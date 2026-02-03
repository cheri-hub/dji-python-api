"""
Extrator final de coordenadas GPS - busca padrão específico DJI
"""
import os
import struct
import json

def find_gps_pairs(data):
    """
    Busca pares de latitude/longitude nos dados.
    Baseado na análise anterior:
    - Latitude: -25.094079 (Brasil, Paraná)
    - Longitude: -48.903534
    """
    gps_points = []
    
    # Procurar por valores double que parecem lat/lon do Brasil (Paraná)
    # Latitude esperada: ~-25 a -24
    # Longitude esperada: ~-49 a -48
    
    i = 0
    while i < len(data) - 16:
        try:
            # Tentar ler dois doubles consecutivos
            val1 = struct.unpack('<d', data[i:i+8])[0]
            val2 = struct.unpack('<d', data[i+8:i+16])[0]
            
            # Verificar se é um par lat/lon válido para a região
            is_lat1 = -26 <= val1 <= -24
            is_lon2 = -50 <= val2 <= -47
            
            if is_lat1 and is_lon2:
                gps_points.append({
                    'lat': val1,
                    'lon': val2,
                    'pos': i
                })
                i += 16  # Pular para próximo possível par
                continue
            
            # Inverter: talvez lon vem antes de lat
            is_lon1 = -50 <= val1 <= -47
            is_lat2 = -26 <= val2 <= -24
            
            if is_lon1 and is_lat2:
                gps_points.append({
                    'lat': val2,
                    'lon': val1,
                    'pos': i
                })
                i += 16
                continue
                
        except:
            pass
        
        i += 1
    
    return gps_points

def remove_duplicates(points, precision=6):
    """Remove pontos duplicados mantendo ordem"""
    seen = set()
    unique = []
    
    for p in points:
        key = (round(p['lat'], precision), round(p['lon'], precision))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    return unique

def main():
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    print("=" * 60)
    print("🗺️ EXTRAINDO COORDENADAS GPS DO VOO DJI - v3")
    print("=" * 60)
    
    with open(route_file, 'rb') as f:
        data = f.read()
    
    print(f"Arquivo: {os.path.basename(route_file)}")
    print(f"Tamanho: {len(data):,} bytes")
    
    # Buscar pares GPS
    print("\n🔍 Buscando pares de coordenadas GPS...")
    points = find_gps_pairs(data)
    print(f"   Pares encontrados: {len(points)}")
    
    if points:
        # Remover duplicatas
        unique_points = remove_duplicates(points)
        print(f"   Pontos únicos: {len(unique_points)}")
        
        # Mostrar primeiros pontos
        print("\n📍 Primeiros 15 pontos da trajetória:")
        for i, p in enumerate(unique_points[:15]):
            print(f"   [{i:4d}] Lat: {p['lat']:.6f}, Lon: {p['lon']:.6f}")
        
        # Estatísticas
        lats = [p['lat'] for p in unique_points]
        lons = [p['lon'] for p in unique_points]
        
        print("\n📊 ESTATÍSTICAS:")
        print(f"   Total pontos: {len(unique_points)}")
        print(f"   Lat min/max: {min(lats):.6f} / {max(lats):.6f}")
        print(f"   Lon min/max: {min(lons):.6f} / {max(lons):.6f}")
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        print(f"   Centro: {center_lat:.6f}, {center_lon:.6f}")
        
        # Google Maps link
        print(f"\n🌍 Ver no Google Maps:")
        print(f"   https://www.google.com/maps/@{center_lat},{center_lon},17z")
        
        # Salvar GeoJSON
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[p['lon'], p['lat']] for p in unique_points]
                    },
                    "properties": {
                        "name": "DJI AG Spray Route",
                        "aircraft": "T40-02",
                        "points": len(unique_points)
                    }
                }
            ]
        }
        
        # Adicionar pontos individuais
        for i, p in enumerate(unique_points):
            if i % max(1, len(unique_points) // 20) == 0:  # ~20 marcadores
                geojson["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [p['lon'], p['lat']]
                    },
                    "properties": {
                        "name": f"Point {i}",
                        "index": i
                    }
                })
        
        geojson_path = os.path.join(records_path, "spray_route.geojson")
        with open(geojson_path, 'w') as f:
            json.dump(geojson, f, indent=2)
        print(f"\n✅ GeoJSON: {geojson_path}")
        
        # CSV
        csv_path = os.path.join(records_path, "spray_route.csv")
        with open(csv_path, 'w') as f:
            f.write("index,latitude,longitude\n")
            for i, p in enumerate(unique_points):
                f.write(f"{i},{p['lat']:.6f},{p['lon']:.6f}\n")
        print(f"✅ CSV: {csv_path}")
        
        # Calcular distância
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000  # metros
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            return R * 2 * atan2(sqrt(a), sqrt(1-a))
        
        total_dist = sum(
            haversine(unique_points[i]['lat'], unique_points[i]['lon'],
                     unique_points[i+1]['lat'], unique_points[i+1]['lon'])
            for i in range(len(unique_points)-1)
        )
        
        print(f"\n📏 Distância total: {total_dist:.0f} metros ({total_dist/1000:.2f} km)")
        
    else:
        print("❌ Nenhum par GPS encontrado")

if __name__ == "__main__":
    main()
