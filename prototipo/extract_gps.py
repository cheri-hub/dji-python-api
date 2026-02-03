"""
Script melhorado para extrair coordenadas GPS dos dados de voo DJI
"""
import os
import struct
import json

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

def extract_all_doubles(data):
    """Extrai todos os valores double (fixed64) do arquivo"""
    pos = 0
    doubles = []
    
    while pos < len(data):
        tag, new_pos = decode_varint(data, pos)
        if tag is None:
            break
        pos = new_pos
        
        wire_type = tag & 0x07
        field_number = tag >> 3
        
        if wire_type == 0:  # VARINT
            _, pos = decode_varint(data, pos)
        elif wire_type == 1:  # FIXED64
            if pos + 8 <= len(data):
                value = struct.unpack('<d', data[pos:pos+8])[0]
                doubles.append({'field': field_number, 'value': value, 'pos': pos})
            pos += 8
        elif wire_type == 2:  # LENGTH_DELIMITED
            length, pos = decode_varint(data, pos)
            if length is None:
                break
            pos += length
        elif wire_type == 5:  # FIXED32
            pos += 4
        else:
            break
    
    return doubles

def extract_gps_coordinates(filepath):
    """Extrai coordenadas GPS do arquivo de dados de voo"""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"Analisando: {os.path.basename(filepath)}")
    print(f"Tamanho: {len(data):,} bytes")
    
    # Extrair todos os doubles
    doubles = extract_all_doubles(data)
    print(f"Total de valores double: {len(doubles)}")
    
    # Filtrar por valores que parecem coordenadas GPS
    # Latitude: -90 a 90
    # Longitude: -180 a 180
    latitudes = []
    longitudes = []
    
    for d in doubles:
        val = d['value']
        if -90 <= val <= 90 and val != 0:
            # Pode ser latitude ou valor pequeno
            if -30 <= val <= 10:  # Faixa do Brasil
                latitudes.append(d)
        if -180 <= val <= -30:  # Longitude no Brasil (oeste)
            longitudes.append(d)
    
    print(f"Possíveis latitudes: {len(latitudes)}")
    print(f"Possíveis longitudes: {len(longitudes)}")
    
    # Mostrar primeiros valores únicos
    unique_lats = list(set([round(d['value'], 6) for d in latitudes]))[:20]
    unique_lons = list(set([round(d['value'], 6) for d in longitudes]))[:20]
    
    print(f"\nLatitudes únicas encontradas:")
    for lat in sorted(unique_lats):
        print(f"   {lat}")
    
    print(f"\nLongitudes únicas encontradas:")
    for lon in sorted(unique_lons):
        print(f"   {lon}")
    
    # Tentar combinar lat/lon por proximidade de posição
    gps_points = []
    
    lat_by_pos = {d['pos']: d['value'] for d in latitudes}
    lon_by_pos = {d['pos']: d['value'] for d in longitudes}
    
    # Geralmente lat e lon estão próximos no arquivo
    for lat_pos, lat_val in sorted(lat_by_pos.items()):
        # Procurar longitude próxima (dentro de 20 bytes)
        for lon_pos, lon_val in lon_by_pos.items():
            if abs(lon_pos - lat_pos) <= 20 and lon_pos > lat_pos:
                gps_points.append({
                    'lat': lat_val,
                    'lon': lon_val,
                    'lat_pos': lat_pos,
                    'lon_pos': lon_pos
                })
                break
    
    print(f"\nPares GPS encontrados: {len(gps_points)}")
    
    # Remover duplicatas
    unique_points = []
    seen = set()
    for p in gps_points:
        key = (round(p['lat'], 5), round(p['lon'], 5))
        if key not in seen:
            seen.add(key)
            unique_points.append(p)
    
    print(f"Pontos únicos: {len(unique_points)}")
    
    if unique_points:
        print("\nPrimeiros 20 pontos GPS:")
        for i, p in enumerate(unique_points[:20]):
            print(f"   [{i}] Lat: {p['lat']:.6f}, Lon: {p['lon']:.6f}")
    
    return unique_points

def save_geojson(points, output_path):
    """Salva pontos como GeoJSON"""
    if not points:
        print("Sem pontos para salvar")
        return
    
    # Criar LineString com a rota
    coordinates = [[p['lon'], p['lat']] for p in points]
    
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                },
                "properties": {
                    "name": "DJI Flight Route",
                    "points": len(points)
                }
            },
            # Adicionar marcadores de início e fim
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": coordinates[0]
                },
                "properties": {
                    "name": "Start",
                    "marker-color": "#00ff00"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": coordinates[-1]
                },
                "properties": {
                    "name": "End",
                    "marker-color": "#ff0000"
                }
            }
        ]
    }
    
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"\n✅ GeoJSON salvo em: {output_path}")
    print(f"   Você pode visualizar em: https://geojson.io/")

def save_csv(points, output_path):
    """Salva pontos como CSV"""
    with open(output_path, 'w') as f:
        f.write("index,latitude,longitude\n")
        for i, p in enumerate(points):
            f.write(f"{i},{p['lat']:.6f},{p['lon']:.6f}\n")
    
    print(f"✅ CSV salvo em: {output_path}")

if __name__ == "__main__":
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    
    # Analisar o arquivo de rota maior
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    if os.path.exists(route_file):
        print("=" * 60)
        print("🗺️ EXTRAINDO COORDENADAS GPS DO VOO")
        print("=" * 60)
        
        points = extract_gps_coordinates(route_file)
        
        if points:
            # Salvar como GeoJSON
            geojson_path = os.path.join(records_path, "flight_route_v2.geojson")
            save_geojson(points, geojson_path)
            
            # Salvar como CSV
            csv_path = os.path.join(records_path, "flight_route.csv")
            save_csv(points, csv_path)
            
            # Estatísticas da rota
            print("\n📊 ESTATÍSTICAS DA ROTA:")
            lats = [p['lat'] for p in points]
            lons = [p['lon'] for p in points]
            print(f"   Latitude: {min(lats):.6f} a {max(lats):.6f}")
            print(f"   Longitude: {min(lons):.6f} a {max(lons):.6f}")
            print(f"   Centro aproximado: {sum(lats)/len(lats):.6f}, {sum(lons)/len(lons):.6f}")
    else:
        print(f"Arquivo não encontrado: {route_file}")
