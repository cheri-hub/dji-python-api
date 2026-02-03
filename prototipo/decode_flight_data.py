"""
Script para decodificar dados de voo DJI (formato protobuf)
"""
import os
import struct
from google.protobuf import descriptor_pb2
from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.internal.wire_format import WIRETYPE_VARINT, WIRETYPE_FIXED64, WIRETYPE_LENGTH_DELIMITED, WIRETYPE_FIXED32

def decode_varint(data, pos):
    """Decodifica um varint do protobuf"""
    result = 0
    shift = 0
    while True:
        if pos >= len(data):
            return None, pos
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos

def decode_protobuf_raw(data, indent=0):
    """Decodifica protobuf raw sem schema"""
    pos = 0
    results = []
    prefix = "  " * indent
    
    while pos < len(data):
        # Ler tag (field_number << 3 | wire_type)
        tag, new_pos = decode_varint(data, pos)
        if tag is None:
            break
        pos = new_pos
        
        field_number = tag >> 3
        wire_type = tag & 0x07
        
        if wire_type == WIRETYPE_VARINT:  # 0
            value, pos = decode_varint(data, pos)
            results.append({
                'field': field_number,
                'type': 'varint',
                'value': value
            })
            
        elif wire_type == WIRETYPE_FIXED64:  # 1
            if pos + 8 > len(data):
                break
            value_bytes = data[pos:pos+8]
            value_double = struct.unpack('<d', value_bytes)[0]
            value_int = struct.unpack('<Q', value_bytes)[0]
            pos += 8
            results.append({
                'field': field_number,
                'type': 'fixed64',
                'value_double': value_double,
                'value_int': value_int
            })
            
        elif wire_type == WIRETYPE_LENGTH_DELIMITED:  # 2
            length, pos = decode_varint(data, pos)
            if length is None or pos + length > len(data):
                break
            value_bytes = data[pos:pos+length]
            pos += length
            
            # Tentar decodificar como string UTF-8
            try:
                value_str = value_bytes.decode('utf-8')
                is_printable = all(c.isprintable() or c in '\n\r\t' for c in value_str)
                if is_printable and len(value_str) > 0:
                    results.append({
                        'field': field_number,
                        'type': 'string',
                        'value': value_str
                    })
                    continue
            except:
                pass
            
            # Tentar decodificar como submessage
            try:
                if len(value_bytes) > 2:
                    sub_results = decode_protobuf_raw(value_bytes, indent + 1)
                    if sub_results and len(sub_results) > 0:
                        results.append({
                            'field': field_number,
                            'type': 'message',
                            'value': sub_results
                        })
                        continue
            except:
                pass
            
            # Bytes raw
            results.append({
                'field': field_number,
                'type': 'bytes',
                'length': len(value_bytes),
                'value': value_bytes[:50].hex() + ('...' if len(value_bytes) > 50 else '')
            })
            
        elif wire_type == WIRETYPE_FIXED32:  # 5
            if pos + 4 > len(data):
                break
            value_bytes = data[pos:pos+4]
            value_float = struct.unpack('<f', value_bytes)[0]
            value_int = struct.unpack('<I', value_bytes)[0]
            pos += 4
            results.append({
                'field': field_number,
                'type': 'fixed32',
                'value_float': value_float,
                'value_int': value_int
            })
        else:
            # Wire type desconhecido, parar
            break
    
    return results

def print_decoded(results, indent=0):
    """Imprime resultados decodificados de forma legível"""
    prefix = "  " * indent
    
    for item in results:
        field = item['field']
        item_type = item['type']
        
        if item_type == 'varint':
            print(f"{prefix}Field {field}: {item['value']} (varint)")
        elif item_type == 'fixed64':
            # Se parece coordenada GPS
            double_val = item['value_double']
            if -180 <= double_val <= 180:
                print(f"{prefix}Field {field}: {double_val:.6f} (fixed64/double - possível coordenada)")
            else:
                print(f"{prefix}Field {field}: {double_val} (fixed64/double)")
        elif item_type == 'fixed32':
            print(f"{prefix}Field {field}: {item['value_float']:.4f} (fixed32/float)")
        elif item_type == 'string':
            print(f"{prefix}Field {field}: \"{item['value']}\" (string)")
        elif item_type == 'bytes':
            print(f"{prefix}Field {field}: [{item['length']} bytes] {item['value']}")
        elif item_type == 'message':
            print(f"{prefix}Field {field}: (submessage)")
            print_decoded(item['value'], indent + 1)

def analyze_flight_data(filepath):
    """Analisa arquivo de dados de voo"""
    print(f"\n{'='*60}")
    print(f"Analisando: {os.path.basename(filepath)}")
    print(f"{'='*60}")
    
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"Tamanho: {len(data):,} bytes")
    print(f"Primeiros 50 bytes (hex): {data[:50].hex()}")
    
    # Decodificar protobuf
    print(f"\n📊 Estrutura Protobuf:")
    print("-" * 40)
    
    try:
        results = decode_protobuf_raw(data)
        
        # Mostrar apenas os primeiros campos
        print(f"Total de campos no nível raiz: {len(results)}")
        print("\nPrimeiros 20 campos:")
        print_decoded(results[:20])
        
        # Analisar tipos de campos
        field_types = {}
        for item in results:
            t = item['type']
            if t not in field_types:
                field_types[t] = 0
            field_types[t] += 1
        
        print(f"\n📈 Estatísticas:")
        for t, count in field_types.items():
            print(f"   {t}: {count} ocorrências")
        
        # Procurar coordenadas GPS
        print(f"\n🌍 Possíveis coordenadas GPS encontradas:")
        gps_count = 0
        for item in results:
            if item['type'] == 'fixed64':
                val = item['value_double']
                if -90 <= val <= 90:  # Latitude
                    print(f"   Latitude? Field {item['field']}: {val:.6f}")
                    gps_count += 1
                elif -180 <= val <= 180:  # Longitude
                    print(f"   Longitude? Field {item['field']}: {val:.6f}")
                    gps_count += 1
            if gps_count >= 10:
                print("   ... (mais coordenadas omitidas)")
                break
        
        return results
        
    except Exception as e:
        print(f"Erro ao decodificar: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_gps_points(filepath):
    """Extrai pontos GPS do arquivo"""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    results = decode_protobuf_raw(data)
    
    gps_points = []
    
    def extract_from_results(items, depth=0):
        lat = None
        lon = None
        
        for item in items:
            if item['type'] == 'fixed64':
                val = item['value_double']
                field = item['field']
                
                # Heurística: campos 2 e 3 geralmente são lat/lon
                if field == 2 and -90 <= val <= 90:
                    lat = val
                elif field == 3 and -180 <= val <= 180:
                    lon = val
                    
            elif item['type'] == 'message':
                extract_from_results(item['value'], depth + 1)
        
        if lat is not None and lon is not None:
            gps_points.append((lat, lon))
    
    extract_from_results(results)
    
    return gps_points

if __name__ == "__main__":
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    
    # Analisar todos os arquivos .bin
    for filename in os.listdir(records_path):
        if filename.endswith('.bin'):
            filepath = os.path.join(records_path, filename)
            results = analyze_flight_data(filepath)
    
    # Tentar extrair pontos GPS do arquivo maior
    print(f"\n{'='*60}")
    print("🗺️ TENTANDO EXTRAIR PONTOS GPS")
    print(f"{'='*60}")
    
    large_file = os.path.join(records_path, "record_0_route_3.bin")
    if os.path.exists(large_file):
        gps_points = extract_gps_points(large_file)
        print(f"\nPontos GPS encontrados: {len(gps_points)}")
        
        if gps_points:
            print("\nPrimeiros 10 pontos:")
            for i, (lat, lon) in enumerate(gps_points[:10]):
                print(f"   [{i}] Lat: {lat:.6f}, Lon: {lon:.6f}")
            
            # Salvar como GeoJSON
            if len(gps_points) > 0:
                geojson = {
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[lon, lat] for lat, lon in gps_points]
                        },
                        "properties": {
                            "name": "Flight Route"
                        }
                    }]
                }
                
                import json
                geojson_path = os.path.join(records_path, "flight_route.geojson")
                with open(geojson_path, 'w') as f:
                    json.dump(geojson, f, indent=2)
                print(f"\n✅ Rota salva em: {geojson_path}")
