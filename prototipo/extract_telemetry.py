"""
Extração estruturada de dados de voo DJI - com telemetria completa
"""
import os
import struct
import json
from collections import defaultdict

def decode_varint(data, pos):
    result, shift = 0, 0
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos

def parse_protobuf_to_records(data, parent_path="", records=None):
    """Parse protobuf extraindo registros de telemetria"""
    if records is None:
        records = []
    
    current_record = {}
    pos = 0
    
    while pos < len(data):
        try:
            tag, new_pos = decode_varint(data, pos)
            if tag is None or new_pos >= len(data):
                break
            pos = new_pos
            
            wire_type = tag & 0x07
            field = tag >> 3
            
            if wire_type == 0:  # VARINT
                val, pos = decode_varint(data, pos)
                current_record[f'int_{field}'] = val
                
            elif wire_type == 1:  # FIXED64 (double)
                if pos + 8 <= len(data):
                    val = struct.unpack('<d', data[pos:pos+8])[0]
                    current_record[f'double_{field}'] = val
                pos += 8
                
            elif wire_type == 2:  # LENGTH_DELIMITED
                length, pos = decode_varint(data, pos)
                if length and pos + length <= len(data):
                    sub_data = data[pos:pos+length]
                    parse_protobuf_to_records(sub_data, f"{parent_path}.{field}", records)
                    pos += length
                else:
                    break
                    
            elif wire_type == 5:  # FIXED32 (float)
                if pos + 4 <= len(data):
                    val = struct.unpack('<f', data[pos:pos+4])[0]
                    current_record[f'float_{field}'] = val
                pos += 4
            else:
                break
                
        except:
            break
    
    # Verificar se é um registro de telemetria (tem lat/lon)
    if 'double_1' in current_record and 'double_2' in current_record:
        lat, lon = current_record.get('double_1'), current_record.get('double_2')
        if -30 < lat < -20 and -55 < lon < -40:
            records.append(current_record)
    
    return records

def extract_telemetry_frames(data):
    """Extrair frames de telemetria completos"""
    frames = []
    pos = 0
    frame_count = 0
    
    # Procurar padrões de frames de telemetria
    while pos < len(data) - 100:
        try:
            # Tentar decodificar um frame
            tag, new_pos = decode_varint(data, pos)
            wire_type = tag & 0x07
            field = tag >> 3
            
            if wire_type == 2:  # Submensagem
                length, length_end = decode_varint(data, new_pos)
                if 50 < length < 1000:  # Tamanho típico de frame de telemetria
                    frame_data = data[length_end:length_end + length]
                    
                    frame = parse_single_frame(frame_data)
                    if frame and 'latitude' in frame:
                        frame['position'] = pos
                        frame['size'] = length
                        frames.append(frame)
                        frame_count += 1
                
                pos = length_end + length
            else:
                pos = new_pos + 8 if wire_type in [1, 5] else new_pos + 4
        except:
            pos += 1
    
    return frames

def parse_single_frame(data):
    """Parse de um único frame de telemetria"""
    frame = {}
    pos = 0
    
    doubles = []
    floats = []
    ints = []
    
    while pos < len(data):
        try:
            tag, new_pos = decode_varint(data, pos)
            if new_pos >= len(data):
                break
            pos = new_pos
            
            wire_type = tag & 0x07
            field = tag >> 3
            
            if wire_type == 0:
                val, pos = decode_varint(data, pos)
                ints.append((field, val))
                
            elif wire_type == 1:  # double
                if pos + 8 <= len(data):
                    val = struct.unpack('<d', data[pos:pos+8])[0]
                    doubles.append((field, val))
                pos += 8
                
            elif wire_type == 2:
                length, pos = decode_varint(data, pos)
                if length and pos + length <= len(data):
                    # Parse submensagem
                    sub_frame = parse_single_frame(data[pos:pos+length])
                    frame.update(sub_frame)
                    pos += length
                else:
                    break
                    
            elif wire_type == 5:  # float
                if pos + 4 <= len(data):
                    val = struct.unpack('<f', data[pos:pos+4])[0]
                    floats.append((field, val))
                pos += 4
            else:
                break
        except:
            break
    
    # Identificar campos
    for field, val in doubles:
        if field == 1 and -30 < val < -20:
            frame['latitude'] = val
        elif field == 2 and -55 < val < -40:
            frame['longitude'] = val
        elif field == 3 and -180 <= val <= 180:
            frame['heading'] = val
        elif field == 28:
            frame['timestamp_ms'] = val
        elif field == 42 and 0 < val < 1:
            frame['spray_ratio'] = val
    
    for field, val in floats:
        if field == 4 and 0 <= val <= 360:
            frame['yaw'] = val
        elif field == 5 and 0 < val < 200:
            frame['altitude'] = val
        elif field == 6 and 0 <= val <= 360:
            frame['gimbal_heading'] = val
        elif field == 39 and val == 100:
            frame['battery_percent'] = val
    
    return frame

def main():
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    print(f"\n{'='*70}")
    print("🚁 EXTRAÇÃO DE TELEMETRIA COMPLETA DJI AG")
    print(f"{'='*70}\n")
    
    with open(route_file, 'rb') as f:
        data = f.read()
    
    print(f"Arquivo: {os.path.basename(route_file)}")
    print(f"Tamanho: {len(data):,} bytes")
    
    # Extrair todos os valores por profundidade para encontrar padrão
    from collections import defaultdict
    
    def extract_all_at_depth(data, target_depth, current_depth=0, values=None):
        """Extrai todos valores de um nível específico"""
        if values is None:
            values = {'doubles': [], 'floats': [], 'ints': []}
        
        pos = 0
        while pos < len(data):
            try:
                tag, new_pos = decode_varint(data, pos)
                if new_pos >= len(data):
                    break
                pos = new_pos
                
                wire_type = tag & 0x07
                field = tag >> 3
                
                if wire_type == 0:  # varint
                    val, pos = decode_varint(data, pos)
                    if current_depth == target_depth:
                        values['ints'].append({'field': field, 'value': val})
                        
                elif wire_type == 1:  # double
                    if pos + 8 <= len(data):
                        val = struct.unpack('<d', data[pos:pos+8])[0]
                        if current_depth == target_depth:
                            values['doubles'].append({'field': field, 'value': val})
                    pos += 8
                    
                elif wire_type == 2:  # submensagem
                    length, pos = decode_varint(data, pos)
                    if length and pos + length <= len(data):
                        extract_all_at_depth(data[pos:pos+length], target_depth, current_depth + 1, values)
                        pos += length
                    else:
                        break
                        
                elif wire_type == 5:  # float
                    if pos + 4 <= len(data):
                        val = struct.unpack('<f', data[pos:pos+4])[0]
                        if current_depth == target_depth:
                            values['floats'].append({'field': field, 'value': val})
                    pos += 4
                else:
                    break
            except:
                break
        
        return values
    
    # Analisar depth 3 onde estão os GPS
    print(f"\n🔍 Analisando depth 3 (onde estão as coordenadas GPS)...")
    values = extract_all_at_depth(data, 3)
    
    print(f"\nDoubles em depth 3: {len(values['doubles'])}")
    print(f"Floats em depth 3: {len(values['floats'])}")
    print(f"Ints em depth 3: {len(values['ints'])}")
    
    # Agrupar por field
    doubles_by_field = defaultdict(list)
    for d in values['doubles']:
        doubles_by_field[d['field']].append(d['value'])
    
    floats_by_field = defaultdict(list)
    for f in values['floats']:
        if -1e10 < f['value'] < 1e10:
            floats_by_field[f['field']].append(f['value'])
    
    ints_by_field = defaultdict(list)
    for i in values['ints']:
        ints_by_field[i['field']].append(i['value'])
    
    print(f"\n{'='*70}")
    print("📊 CAMPOS IDENTIFICADOS (depth 3)")
    print(f"{'='*70}")
    
    print("\n🔢 DOUBLES:")
    for field in sorted(doubles_by_field.keys()):
        vals = doubles_by_field[field]
        print(f"   Field {field:2d}: {len(vals):5d} valores | "
              f"min: {min(vals):12.4f} | max: {max(vals):12.4f} | "
              f"média: {sum(vals)/len(vals):12.4f}")
    
    print("\n🔢 FLOATS:")
    for field in sorted(floats_by_field.keys()):
        vals = floats_by_field[field]
        if len(vals) < 100:
            continue
        print(f"   Field {field:2d}: {len(vals):5d} valores | "
              f"min: {min(vals):12.4f} | max: {max(vals):12.4f} | "
              f"média: {sum(vals)/len(vals):12.4f}")
    
    print("\n🔢 INTS:")
    for field in sorted(ints_by_field.keys()):
        vals = ints_by_field[field]
        if len(vals) < 100 or max(vals) > 1e15:
            continue
        unique = len(set(vals))
        print(f"   Field {field:2d}: {len(vals):5d} valores | "
              f"únicos: {unique:4d} | "
              f"min: {min(vals):10d} | max: {max(vals):10d}")
    
    # Correlacionar dados - criar frames de telemetria
    print(f"\n{'='*70}")
    print("🚁 MONTANDO FRAMES DE TELEMETRIA")
    print(f"{'='*70}")
    
    # Assumindo que os dados estão ordenados:
    # - Latitude (field 1)
    # - Longitude (field 2)  
    # - Heading (field 3)
    # - outros campos...
    
    lats = doubles_by_field.get(1, [])
    lons = doubles_by_field.get(2, [])
    headings = doubles_by_field.get(3, [])
    
    # Filtrar para região válida
    valid_lats = [v for v in lats if -30 < v < -20]
    valid_lons = [v for v in lons if -55 < v < -40]
    
    print(f"\nLatitudes válidas: {len(valid_lats)}")
    print(f"Longitudes válidas: {len(valid_lons)}")
    print(f"Headings: {len(headings)}")
    
    # Encontrar floats que parecem altitude
    altitudes = floats_by_field.get(5, [])
    valid_alts = [v for v in altitudes if 0 < v < 200]
    print(f"Altitudes válidas (field 5): {len(valid_alts)}")
    if valid_alts:
        print(f"   Range: {min(valid_alts):.1f}m a {max(valid_alts):.1f}m")
    
    # Criar frames emparelhando os dados
    num_frames = min(len(valid_lats), len(valid_lons))
    
    telemetry = []
    for i in range(num_frames):
        frame = {
            'index': i,
            'latitude': valid_lats[i],
            'longitude': valid_lons[i],
        }
        
        if i < len(headings):
            frame['heading'] = headings[i]
        
        if i < len(valid_alts):
            frame['altitude'] = valid_alts[i]
        
        telemetry.append(frame)
    
    print(f"\n✅ {len(telemetry)} frames de telemetria montados")
    
    # Estatísticas
    print(f"\n{'='*70}")
    print("📈 ESTATÍSTICAS DA MISSÃO")
    print(f"{'='*70}")
    
    if telemetry:
        print(f"\n📍 POSIÇÃO:")
        print(f"   Latitude:  {min(f['latitude'] for f in telemetry):.6f} a {max(f['latitude'] for f in telemetry):.6f}")
        print(f"   Longitude: {min(f['longitude'] for f in telemetry):.6f} a {max(f['longitude'] for f in telemetry):.6f}")
        
        if 'heading' in telemetry[0]:
            headings = [f['heading'] for f in telemetry if 'heading' in f]
            print(f"\n🧭 HEADING (direção):")
            print(f"   Min: {min(headings):.1f}° | Max: {max(headings):.1f}° | Média: {sum(headings)/len(headings):.1f}°")
        
        if valid_alts:
            print(f"\n📏 ALTITUDE:")
            print(f"   Min: {min(valid_alts):.1f}m | Max: {max(valid_alts):.1f}m | Média: {sum(valid_alts)/len(valid_alts):.1f}m")
    
    # Procurar no depth 2 por parâmetros de missão
    print(f"\n{'='*70}")
    print("🔍 Analisando depth 2 (parâmetros de missão)...")
    print(f"{'='*70}")
    
    values_d2 = extract_all_at_depth(data, 2)
    
    floats_d2 = defaultdict(list)
    for f in values_d2['floats']:
        if -1e10 < f['value'] < 1e10:
            floats_d2[f['field']].append(f['value'])
    
    print("\n🔢 FLOATS em depth 2:")
    for field in sorted(floats_d2.keys()):
        vals = floats_d2[field]
        if len(vals) < 50:
            continue
        unique = set(round(v, 1) for v in vals)
        if len(unique) < 20:
            print(f"   Field {field:2d}: {len(vals):5d} valores | "
                  f"valores únicos: {sorted(unique)[:10]}")
    
    # Salvar telemetria completa
    output_path = os.path.join(records_path, "telemetry_complete.json")
    with open(output_path, 'w') as f:
        json.dump({
            'mission_summary': {
                'total_frames': len(telemetry),
                'lat_range': [min(f['latitude'] for f in telemetry), max(f['latitude'] for f in telemetry)] if telemetry else [],
                'lon_range': [min(f['longitude'] for f in telemetry), max(f['longitude'] for f in telemetry)] if telemetry else [],
                'alt_range': [min(valid_alts), max(valid_alts)] if valid_alts else [],
            },
            'telemetry': telemetry[:100],  # Primeiros 100 para amostra
        }, f, indent=2)
    
    print(f"\n✅ Telemetria salva em: {output_path}")

if __name__ == "__main__":
    main()
