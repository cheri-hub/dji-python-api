"""
Análise completa dos dados de voo DJI - extrair todos os campos
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

def parse_protobuf_full(data, depth=0, path="root", collected=None):
    """Parse protobuf coletando TODOS os valores com seus caminhos"""
    if collected is None:
        collected = {
            'doubles': [],
            'floats': [],
            'varints': [],
            'strings': [],
        }
    
    pos = 0
    field_index = 0
    
    while pos < len(data):
        try:
            tag, new_pos = decode_varint(data, pos)
            if tag is None or new_pos >= len(data):
                break
            pos = new_pos
            
            wire_type = tag & 0x07
            field = tag >> 3
            current_path = f"{path}.{field}"
            
            if wire_type == 0:  # VARINT
                val, pos = decode_varint(data, pos)
                collected['varints'].append({
                    'path': current_path,
                    'field': field,
                    'depth': depth,
                    'value': val,
                    'index': field_index
                })
                
            elif wire_type == 1:  # FIXED64 (double)
                if pos + 8 <= len(data):
                    val = struct.unpack('<d', data[pos:pos+8])[0]
                    collected['doubles'].append({
                        'path': current_path,
                        'field': field,
                        'depth': depth,
                        'value': val,
                        'index': field_index
                    })
                pos += 8
                
            elif wire_type == 2:  # LENGTH_DELIMITED
                length, pos = decode_varint(data, pos)
                if length and pos + length <= len(data):
                    sub_data = data[pos:pos+length]
                    
                    # Tentar decodificar como string
                    try:
                        text = sub_data.decode('utf-8')
                        if text.isprintable() and len(text) > 0:
                            collected['strings'].append({
                                'path': current_path,
                                'field': field,
                                'depth': depth,
                                'value': text,
                                'index': field_index
                            })
                    except:
                        pass
                    
                    # Parsear como submensagem
                    parse_protobuf_full(sub_data, depth + 1, current_path, collected)
                    pos += length
                else:
                    break
                    
            elif wire_type == 5:  # FIXED32 (float)
                if pos + 4 <= len(data):
                    val = struct.unpack('<f', data[pos:pos+4])[0]
                    collected['floats'].append({
                        'path': current_path,
                        'field': field,
                        'depth': depth,
                        'value': val,
                        'index': field_index
                    })
                pos += 4
            else:
                break
                
            field_index += 1
        except:
            break
    
    return collected

def analyze_flight_data(filepath):
    """Analisa dados de voo extraindo todas as informações"""
    print(f"\n{'='*70}")
    print(f"📊 ANÁLISE COMPLETA: {os.path.basename(filepath)}")
    print(f"{'='*70}")
    
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"Tamanho: {len(data):,} bytes\n")
    
    # Parsear tudo
    collected = parse_protobuf_full(data)
    
    print(f"📈 Estatísticas gerais:")
    print(f"   Doubles (float64): {len(collected['doubles'])}")
    print(f"   Floats (float32): {len(collected['floats'])}")
    print(f"   Varints (integers): {len(collected['varints'])}")
    print(f"   Strings: {len(collected['strings'])}")
    
    # Analisar doubles
    print(f"\n{'='*70}")
    print("🔢 ANÁLISE DE VALORES DOUBLE")
    print(f"{'='*70}")
    
    # Agrupar por campo
    doubles_by_field = defaultdict(list)
    for d in collected['doubles']:
        doubles_by_field[d['field']].append(d['value'])
    
    print("\nCampos double encontrados:")
    for field in sorted(doubles_by_field.keys()):
        values = doubles_by_field[field]
        unique = set(round(v, 4) for v in values)
        min_v, max_v = min(values), max(values)
        avg_v = sum(values) / len(values)
        
        # Identificar tipo de dado
        data_type = ""
        if -90 <= min_v and max_v <= 90 and abs(avg_v) > 20:
            data_type = "← LATITUDE?"
        elif -180 <= min_v and max_v <= 180 and min_v < -40:
            data_type = "← LONGITUDE?"
        elif 0 < avg_v < 10:
            data_type = "← velocidade/taxa?"
        elif 50 < avg_v < 200:
            data_type = "← altitude?"
        
        print(f"   Field {field:2d}: {len(values):6d} valores | "
              f"min: {min_v:12.4f} | max: {max_v:12.4f} | "
              f"avg: {avg_v:12.4f} {data_type}")
    
    # Analisar floats
    print(f"\n{'='*70}")
    print("🔢 ANÁLISE DE VALORES FLOAT")
    print(f"{'='*70}")
    
    floats_by_field = defaultdict(list)
    for f in collected['floats']:
        floats_by_field[f['field']].append(f['value'])
    
    print("\nCampos float encontrados:")
    for field in sorted(floats_by_field.keys()):
        values = floats_by_field[field]
        # Filtrar valores inválidos
        valid = [v for v in values if -1e10 < v < 1e10]
        if not valid:
            continue
        
        min_v, max_v = min(valid), max(valid)
        avg_v = sum(valid) / len(valid)
        
        # Identificar tipo de dado
        data_type = ""
        if 80 < avg_v < 120:
            data_type = "← possível porcentagem ou altitude"
        elif 0 < avg_v < 30:
            data_type = "← velocidade/taxa?"
        elif 0 <= min_v and max_v <= 360:
            data_type = "← ângulo/heading?"
        
        print(f"   Field {field:2d}: {len(valid):6d} valores | "
              f"min: {min_v:12.4f} | max: {max_v:12.4f} | "
              f"avg: {avg_v:12.4f} {data_type}")
    
    # Analisar varints
    print(f"\n{'='*70}")
    print("🔢 ANÁLISE DE VALORES INTEIROS (VARINT)")
    print(f"{'='*70}")
    
    varints_by_field = defaultdict(list)
    for v in collected['varints']:
        varints_by_field[v['field']].append(v['value'])
    
    print("\nCampos varint mais significativos:")
    for field in sorted(varints_by_field.keys()):
        values = varints_by_field[field]
        if len(values) < 10:
            continue
        
        unique = set(values)
        min_v, max_v = min(values), max(values)
        
        # Identificar tipo
        data_type = ""
        if len(unique) <= 5:
            data_type = f"← enum? valores: {sorted(unique)[:5]}"
        elif 0 < min_v < 1000 and max_v < 100000:
            data_type = "← contador/timestamp?"
        
        if len(unique) <= 20 or max_v > 1000:
            print(f"   Field {field:2d}: {len(values):6d} valores | "
                  f"únicos: {len(unique):4d} | "
                  f"min: {min_v:10d} | max: {max_v:10d} {data_type}")
    
    # Analisar strings
    print(f"\n{'='*70}")
    print("📝 STRINGS ENCONTRADAS")
    print(f"{'='*70}")
    
    unique_strings = set()
    for s in collected['strings']:
        if len(s['value']) > 2:
            unique_strings.add(s['value'])
    
    print(f"\nStrings únicas ({len(unique_strings)}):")
    for s in sorted(unique_strings)[:30]:
        print(f"   '{s}'")
    
    # Análise específica para dados de pulverização
    print(f"\n{'='*70}")
    print("🚁 IDENTIFICAÇÃO DE DADOS DE VOO/PULVERIZAÇÃO")
    print(f"{'='*70}")
    
    # Procurar valores típicos
    # Spray Flow Rate: geralmente 1-10 L/min
    # Route Spacing: geralmente 3-10 metros
    # Task Speed: geralmente 3-15 m/s
    
    print("\n🔍 Possíveis valores de SPRAY FLOW RATE (1-10 L/min):")
    for d in collected['doubles'][:50]:
        if 0.5 < d['value'] < 15:
            print(f"   Field {d['field']}: {d['value']:.2f}")
    
    for f in collected['floats'][:50]:
        if 0.5 < f['value'] < 15:
            print(f"   Field {f['field']}: {f['value']:.2f}")
    
    print("\n🔍 Possíveis valores de ROUTE SPACING (2-10 m):")
    spacing_candidates = [d for d in collected['doubles'] if 2 < d['value'] < 12]
    unique_spacing = set(round(d['value'], 1) for d in spacing_candidates[:100])
    for v in sorted(unique_spacing)[:10]:
        count = len([d for d in spacing_candidates if abs(d['value'] - v) < 0.5])
        print(f"   {v:.1f}m ({count} ocorrências)")
    
    print("\n🔍 Possíveis valores de TASK SPEED (2-20 m/s):")
    speed_candidates = [d for d in collected['doubles'] if 2 < d['value'] < 25]
    unique_speeds = set(round(d['value'], 1) for d in speed_candidates[:100])
    for v in sorted(unique_speeds)[:10]:
        count = len([d for d in speed_candidates if abs(d['value'] - v) < 0.5])
        print(f"   {v:.1f} m/s ({count} ocorrências)")
    
    # Procurar altitude
    print("\n🔍 Possíveis valores de ALTITUDE (5-50 m):")
    alt_candidates = [f for f in collected['floats'] if 5 < f['value'] < 100]
    unique_alts = set(round(f['value'], 0) for f in alt_candidates[:200])
    for v in sorted(unique_alts)[:10]:
        count = len([f for f in alt_candidates if abs(f['value'] - v) < 2])
        print(f"   {v:.0f}m ({count} ocorrências)")
    
    return collected

def main():
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    if os.path.exists(route_file):
        collected = analyze_flight_data(route_file)
        
        # Salvar análise completa em JSON
        analysis = {
            'doubles_summary': {},
            'floats_summary': {},
            'strings': list(set(s['value'] for s in collected['strings'] if len(s['value']) > 2))
        }
        
        # Resumir doubles
        doubles_by_field = defaultdict(list)
        for d in collected['doubles']:
            doubles_by_field[d['field']].append(d['value'])
        
        for field, values in doubles_by_field.items():
            analysis['doubles_summary'][str(field)] = {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'sample': values[:5]
            }
        
        # Resumir floats
        floats_by_field = defaultdict(list)
        for f in collected['floats']:
            floats_by_field[f['field']].append(f['value'])
        
        for field, values in floats_by_field.items():
            valid = [v for v in values if -1e10 < v < 1e10]
            if valid:
                analysis['floats_summary'][str(field)] = {
                    'count': len(valid),
                    'min': min(valid),
                    'max': max(valid),
                    'avg': sum(valid) / len(valid),
                    'sample': valid[:5]
                }
        
        # Salvar
        analysis_path = os.path.join(records_path, "flight_data_analysis.json")
        with open(analysis_path, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"\n✅ Análise completa salva em: {analysis_path}")

if __name__ == "__main__":
    main()
