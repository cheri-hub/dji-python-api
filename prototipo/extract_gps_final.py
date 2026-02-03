"""
Extrator baseado na estrutura protobuf real encontrada
"""
import os
import struct
import json

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

def parse_protobuf_recursive(data, depth=0, collected_doubles=[]):
    """Parse protobuf recursivamente coletando todos os doubles"""
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
                _, pos = decode_varint(data, pos)
            elif wire_type == 1:  # FIXED64
                if pos + 8 <= len(data):
                    val = struct.unpack('<d', data[pos:pos+8])[0]
                    collected_doubles.append({
                        'field': field,
                        'value': val,
                        'depth': depth
                    })
                pos += 8
            elif wire_type == 2:  # LENGTH_DELIMITED
                length, pos = decode_varint(data, pos)
                if length and pos + length <= len(data):
                    # Tentar parsear como submensagem
                    sub_data = data[pos:pos+length]
                    parse_protobuf_recursive(sub_data, depth + 1, collected_doubles)
                    pos += length
                else:
                    break
            elif wire_type == 5:  # FIXED32
                pos += 4
            else:
                break
        except:
            break
    
    return collected_doubles

def main():
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    print("=" * 60)
    print("🗺️ ANÁLISE PROFUNDA DO PROTOBUF DJI")
    print("=" * 60)
    
    with open(route_file, 'rb') as f:
        data = f.read()
    
    print(f"Arquivo: {os.path.basename(route_file)}")
    print(f"Tamanho: {len(data):,} bytes")
    
    # Coletar todos os doubles
    print("\n🔍 Parseando protobuf recursivamente...")
    doubles = []
    parse_protobuf_recursive(data, 0, doubles)
    
    print(f"   Total de valores double encontrados: {len(doubles)}")
    
    # Filtrar por valores que parecem coordenadas
    latitudes = [d for d in doubles if -26 <= d['value'] <= -24]
    longitudes = [d for d in doubles if -50 <= d['value'] <= -47]
    
    print(f"   Possíveis latitudes (-26 a -24): {len(latitudes)}")
    print(f"   Possíveis longitudes (-50 a -47): {len(longitudes)}")
    
    if latitudes:
        print("\n📍 Primeiras 20 latitudes:")
        for i, d in enumerate(latitudes[:20]):
            print(f"   Field {d['field']}, depth {d['depth']}: {d['value']:.6f}")
    
    if longitudes:
        print("\n📍 Primeiras 20 longitudes:")
        for i, d in enumerate(longitudes[:20]):
            print(f"   Field {d['field']}, depth {d['depth']}: {d['value']:.6f}")
    
    # Tentar combinar lat/lon pelo campo number
    # A análise anterior mostrou Field 1 = lat, Field 2 = lon em submensagens
    print("\n📊 Analisando padrão de campos...")
    
    field_1_vals = [d['value'] for d in doubles if d['field'] == 1]
    field_2_vals = [d['value'] for d in doubles if d['field'] == 2]
    
    # Filtrar por coordenadas válidas
    lat_field1 = [v for v in field_1_vals if -26 <= v <= -24]
    lon_field2 = [v for v in field_2_vals if -50 <= v <= -47]
    
    print(f"   Field 1 com latitudes: {len(lat_field1)}")
    print(f"   Field 2 com longitudes: {len(lon_field2)}")
    
    # Parear coordenadas
    min_pairs = min(len(lat_field1), len(lon_field2))
    if min_pairs > 0:
        print(f"\n🎯 Pareando {min_pairs} coordenadas...")
        
        gps_points = []
        for i in range(min_pairs):
            gps_points.append({
                'lat': lat_field1[i],
                'lon': lon_field2[i]
            })
        
        # Mostrar primeiros pontos
        print("\n📍 Primeiros 20 pontos da rota:")
        for i, p in enumerate(gps_points[:20]):
            print(f"   [{i:4d}] Lat: {p['lat']:.6f}, Lon: {p['lon']:.6f}")
        
        # Estatísticas
        lats = [p['lat'] for p in gps_points]
        lons = [p['lon'] for p in gps_points]
        
        print("\n📊 ESTATÍSTICAS:")
        print(f"   Total pontos: {len(gps_points)}")
        print(f"   Lat: {min(lats):.6f} a {max(lats):.6f}")
        print(f"   Lon: {min(lons):.6f} a {max(lons):.6f}")
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        print(f"   Centro: {center_lat:.6f}, {center_lon:.6f}")
        
        # Google Maps
        print(f"\n🌍 Google Maps: https://www.google.com/maps/@{center_lat},{center_lon},17z")
        
        # Remover duplicatas consecutivas para ter trajetória limpa
        trajectory = [gps_points[0]]
        for p in gps_points[1:]:
            if abs(p['lat'] - trajectory[-1]['lat']) > 0.000001 or \
               abs(p['lon'] - trajectory[-1]['lon']) > 0.000001:
                trajectory.append(p)
        
        print(f"\n📍 Trajetória filtrada: {len(trajectory)} pontos")
        
        # Salvar GeoJSON
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[p['lon'], p['lat']] for p in trajectory]
                    },
                    "properties": {
                        "name": "DJI T40-02 Spray Route",
                        "points": len(trajectory)
                    }
                }
            ]
        }
        
        geojson_path = os.path.join(records_path, "dji_route.geojson")
        with open(geojson_path, 'w') as f:
            json.dump(geojson, f, indent=2)
        print(f"\n✅ GeoJSON: {geojson_path}")
        
        # CSV
        csv_path = os.path.join(records_path, "dji_route.csv")
        with open(csv_path, 'w') as f:
            f.write("index,latitude,longitude\n")
            for i, p in enumerate(trajectory):
                f.write(f"{i},{p['lat']:.6f},{p['lon']:.6f}\n")
        print(f"✅ CSV: {csv_path}")
        
        # Calcular distância
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            return R * 2 * atan2(sqrt(a), sqrt(1-a))
        
        total_dist = sum(
            haversine(trajectory[i]['lat'], trajectory[i]['lon'],
                     trajectory[i+1]['lat'], trajectory[i+1]['lon'])
            for i in range(len(trajectory)-1)
        )
        
        print(f"\n📏 Distância total: {total_dist:.2f} km")
        print(f"\n🌐 Visualize: https://geojson.io/")

if __name__ == "__main__":
    main()
