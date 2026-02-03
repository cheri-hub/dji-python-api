"""
Extrator recursivo de coordenadas GPS dos dados de voo DJI
"""
import os
import struct
import json

def scan_for_gps_pattern(data):
    """
    Escaneia o arquivo binário procurando padrões de coordenadas GPS.
    Coordenadas GPS são armazenadas como double (8 bytes) em formato little-endian.
    Latitude: -90 a 90
    Longitude: -180 a 180
    """
    gps_points = []
    
    # Procurar padrões onde temos dois doubles consecutivos que parecem lat/lon
    for i in range(0, len(data) - 16, 1):
        try:
            val1 = struct.unpack('<d', data[i:i+8])[0]
            val2 = struct.unpack('<d', data[i+8:i+16])[0]
            
            # Verificar se parece coordenada GPS no Brasil
            # Latitude do Brasil: aproximadamente -34 a 5
            # Longitude do Brasil: aproximadamente -74 a -34
            if -35 <= val1 <= 10 and -75 <= val2 <= -30:
                # Parece uma coordenada válida do Brasil
                gps_points.append({
                    'lat': val1,
                    'lon': val2,
                    'pos': i
                })
        except:
            continue
    
    return gps_points

def filter_trajectory_points(points, min_distance=0.00001):
    """Filtra pontos mantendo apenas a trajetória (remove duplicatas muito próximas)"""
    if not points:
        return []
    
    filtered = [points[0]]
    
    for p in points[1:]:
        last = filtered[-1]
        dist = abs(p['lat'] - last['lat']) + abs(p['lon'] - last['lon'])
        if dist > min_distance:
            filtered.append(p)
    
    return filtered

def main():
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    print("=" * 60)
    print("🗺️ EXTRAINDO COORDENADAS GPS DO VOO DJI")
    print("=" * 60)
    
    with open(route_file, 'rb') as f:
        data = f.read()
    
    print(f"Arquivo: {os.path.basename(route_file)}")
    print(f"Tamanho: {len(data):,} bytes")
    
    # Escanear por padrões GPS
    print("\n🔍 Escaneando arquivo por coordenadas GPS...")
    raw_points = scan_for_gps_pattern(data)
    print(f"   Pontos brutos encontrados: {len(raw_points)}")
    
    if raw_points:
        # Filtrar trajetória
        print("\n📍 Filtrando trajetória...")
        trajectory = filter_trajectory_points(raw_points, min_distance=0.000005)
        print(f"   Pontos na trajetória: {len(trajectory)}")
        
        if trajectory:
            # Mostrar primeiros e últimos pontos
            print("\n📍 Primeiros 10 pontos:")
            for i, p in enumerate(trajectory[:10]):
                print(f"   [{i}] Lat: {p['lat']:.6f}, Lon: {p['lon']:.6f}")
            
            print("\n📍 Últimos 10 pontos:")
            for i, p in enumerate(trajectory[-10:]):
                print(f"   [{len(trajectory)-10+i}] Lat: {p['lat']:.6f}, Lon: {p['lon']:.6f}")
            
            # Estatísticas
            lats = [p['lat'] for p in trajectory]
            lons = [p['lon'] for p in trajectory]
            
            print("\n📊 ESTATÍSTICAS DA ROTA:")
            print(f"   Total de pontos: {len(trajectory)}")
            print(f"   Latitude: {min(lats):.6f} a {max(lats):.6f}")
            print(f"   Longitude: {min(lons):.6f} a {max(lons):.6f}")
            print(f"   Centro: {sum(lats)/len(lats):.6f}, {sum(lons)/len(lons):.6f}")
            
            # Salvar como GeoJSON
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
                            "name": "DJI AG Flight Route",
                            "points": len(trajectory),
                            "aircraft": "T40-02"
                        }
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [trajectory[0]['lon'], trajectory[0]['lat']]
                        },
                        "properties": {
                            "name": "Start Point",
                            "marker-color": "#00ff00",
                            "marker-symbol": "airport"
                        }
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [trajectory[-1]['lon'], trajectory[-1]['lat']]
                        },
                        "properties": {
                            "name": "End Point",
                            "marker-color": "#ff0000",
                            "marker-symbol": "circle"
                        }
                    }
                ]
            }
            
            geojson_path = os.path.join(records_path, "flight_route_final.geojson")
            with open(geojson_path, 'w') as f:
                json.dump(geojson, f, indent=2)
            print(f"\n✅ GeoJSON salvo: {geojson_path}")
            
            # Salvar como CSV
            csv_path = os.path.join(records_path, "flight_route_final.csv")
            with open(csv_path, 'w') as f:
                f.write("index,latitude,longitude\n")
                for i, p in enumerate(trajectory):
                    f.write(f"{i},{p['lat']:.6f},{p['lon']:.6f}\n")
            print(f"✅ CSV salvo: {csv_path}")
            
            # Calcular distância aproximada percorrida
            from math import radians, sin, cos, sqrt, atan2
            
            def haversine(lat1, lon1, lat2, lon2):
                R = 6371  # Raio da Terra em km
                lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                return R * c
            
            total_distance = 0
            for i in range(1, len(trajectory)):
                total_distance += haversine(
                    trajectory[i-1]['lat'], trajectory[i-1]['lon'],
                    trajectory[i]['lat'], trajectory[i]['lon']
                )
            
            print(f"\n📏 Distância total percorrida: {total_distance:.2f} km")
            print(f"🌐 Visualize a rota em: https://geojson.io/")
            
    else:
        print("❌ Nenhuma coordenada GPS encontrada")

if __name__ == "__main__":
    main()
