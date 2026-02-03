"""
Gerar GeoJSON enriquecido com todos os metadados de telemetria
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

def extract_all_values(data, max_depth=6):
    all_values = defaultdict(lambda: defaultdict(list))
    
    def parse_recursive(data, depth=0):
        if depth > max_depth:
            return
        pos = 0
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
                    if val < 1e15:
                        all_values[depth][f'int_{field}'].append(val)
                elif wire_type == 1:
                    if pos + 8 <= len(data):
                        val = struct.unpack('<d', data[pos:pos+8])[0]
                        if -1e10 < val < 1e10:
                            all_values[depth][f'dbl_{field}'].append(val)
                    pos += 8
                elif wire_type == 2:
                    length, pos = decode_varint(data, pos)
                    if length and pos + length <= len(data):
                        parse_recursive(data[pos:pos+length], depth + 1)
                        pos += length
                    else:
                        break
                elif wire_type == 5:
                    if pos + 4 <= len(data):
                        val = struct.unpack('<f', data[pos:pos+4])[0]
                        if -1e10 < val < 1e10:
                            all_values[depth][f'flt_{field}'].append(val)
                    pos += 4
                else:
                    break
            except:
                break
    
    parse_recursive(data)
    return all_values

def main():
    records_path = os.path.join(os.path.dirname(__file__), "downloads", "records")
    route_file = os.path.join(records_path, "record_0_route_3.bin")
    
    print("🚁 Gerando GeoJSON enriquecido com metadados...\n")
    
    with open(route_file, 'rb') as f:
        data = f.read()
    
    all_values = extract_all_values(data)
    
    # Extrair dados
    latitudes = [v for v in all_values[3]['dbl_1'] if -30 < v < -20]
    longitudes = [v for v in all_values[3]['dbl_2'] if -55 < v < -40]
    headings = [h for h in all_values[3]['dbl_3'] if -180 <= h <= 180]
    
    vel_x = [v for v in all_values[3]['flt_1'] if -15 < v < 15]
    vel_y = [v for v in all_values[3]['flt_2'] if -15 < v < 15]
    spray_values = [v for v in all_values[3]['flt_3'] if 0 < v < 20]
    
    # Parâmetros de missão
    battery = all_values[2]['flt_39'][0] if all_values[2]['flt_39'] else None
    task_speed = all_values[2]['int_10'][0] if all_values[2]['int_10'] else None
    route_spacing = all_values[3]['int_7'][0] if all_values[3]['int_7'] else None
    mission_code = all_values[2]['int_23'][0] if all_values[2]['int_23'] else None
    
    # Ler Flight Record Number do arquivo de análise
    analysis_file = os.path.join(records_path, "record_0_analysis.json")
    flight_record_number = None
    if os.path.exists(analysis_file):
        with open(analysis_file, 'r') as f:
            analysis = json.load(f)
            record_url = analysis.get('record_url', '')
            if record_url:
                # Extrair número da URL: https://www.djiag.com/record/531405271
                flight_record_number = record_url.split('/')[-1]
    
    num_points = min(len(latitudes), len(longitudes))
    
    print(f"📍 Pontos GPS: {num_points}")
    print(f"🧭 Headings: {len(headings)}")
    print(f"🚀 Velocidades: {len(vel_x)} x {len(vel_y)}")
    print(f"💧 Spray rates: {len(spray_values)}")
    
    # Criar features individuais para cada ponto (com propriedades)
    point_features = []
    for i in range(num_points):
        properties = {
            "index": i,
            "latitude": latitudes[i],
            "longitude": longitudes[i],
        }
        
        if i < len(headings):
            properties["heading"] = round(headings[i], 2)
        if i < len(vel_x):
            properties["velocity_x"] = round(vel_x[i], 2)
        if i < len(vel_y):
            properties["velocity_y"] = round(vel_y[i], 2)
        if i < len(spray_values):
            properties["spray_rate"] = round(spray_values[i], 2)
        
        # Calcular velocidade total
        if i < len(vel_x) and i < len(vel_y):
            speed = (vel_x[i]**2 + vel_y[i]**2)**0.5
            properties["speed_ms"] = round(speed, 2)
        
        point_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [longitudes[i], latitudes[i]]
            },
            "properties": properties
        })
    
    # Criar linha da rota
    route_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[longitudes[i], latitudes[i]] for i in range(num_points)]
        },
        "properties": {
            "type": "flight_path",
            "total_points": num_points,
            "description": "DJI AG Flight Route"
        }
    }
    
    # Calcular estatísticas
    avg_heading = sum(headings) / len(headings) if headings else 0
    avg_spray = sum(spray_values) / len(spray_values) if spray_values else 0
    
    speeds = []
    for i in range(min(len(vel_x), len(vel_y))):
        speeds.append((vel_x[i]**2 + vel_y[i]**2)**0.5)
    avg_speed = sum(speeds) / len(speeds) if speeds else 0
    
    # GeoJSON completo
    geojson = {
        "type": "FeatureCollection",
        "name": "DJI AG Flight Data",
        "properties": {
            "mission": {
                "flight_record_number": flight_record_number,
                "code": mission_code,
                "total_points": num_points,
                "battery_percent": battery,
                "task_speed": task_speed,
                "route_spacing": route_spacing,
            },
            "gps": {
                "lat_min": min(latitudes),
                "lat_max": max(latitudes),
                "lon_min": min(longitudes),
                "lon_max": max(longitudes),
                "center_lat": (min(latitudes) + max(latitudes)) / 2,
                "center_lon": (min(longitudes) + max(longitudes)) / 2,
            },
            "telemetry": {
                "heading_avg": round(avg_heading, 2),
                "heading_min": round(min(headings), 2) if headings else None,
                "heading_max": round(max(headings), 2) if headings else None,
                "speed_avg_ms": round(avg_speed, 2),
                "speed_max_ms": round(max(speeds), 2) if speeds else None,
                "spray_rate_avg": round(avg_spray, 2),
                "spray_rate_min": round(min(spray_values), 2) if spray_values else None,
                "spray_rate_max": round(max(spray_values), 2) if spray_values else None,
                "velocity_x_range": [round(min(vel_x), 2), round(max(vel_x), 2)] if vel_x else None,
                "velocity_y_range": [round(min(vel_y), 2), round(max(vel_y), 2)] if vel_y else None,
            }
        },
        "features": [route_feature] + point_features
    }
    
    # Salvar
    output_path = os.path.join(records_path, "mission_complete.geojson")
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"\n✅ GeoJSON salvo: {output_path}")
    print(f"   📦 {len(geojson['features'])} features (1 rota + {num_points} pontos)")
    
    # Resumo
    print(f"\n{'='*60}")
    print("📋 METADADOS INCLUÍDOS NO GEOJSON:")
    print(f"{'='*60}")
    print(f"\n⚙️ MISSÃO:")
    print(f"   Flight Record Number: {flight_record_number}")
    print(f"   Código: {mission_code}")
    print(f"   Task Speed: {task_speed} m/s")
    print(f"   Route Spacing: {route_spacing}m")
    print(f"   Bateria: {battery}%")
    
    print(f"\n📍 GPS:")
    print(f"   Centro: {geojson['properties']['gps']['center_lat']:.6f}, {geojson['properties']['gps']['center_lon']:.6f}")
    
    print(f"\n📊 TELEMETRIA:")
    print(f"   Heading: {geojson['properties']['telemetry']['heading_min']}° a {geojson['properties']['telemetry']['heading_max']}° (média: {geojson['properties']['telemetry']['heading_avg']}°)")
    print(f"   Velocidade: até {geojson['properties']['telemetry']['speed_max_ms']} m/s (média: {geojson['properties']['telemetry']['speed_avg_ms']} m/s)")
    print(f"   Spray Rate: {geojson['properties']['telemetry']['spray_rate_min']} a {geojson['properties']['telemetry']['spray_rate_max']} (média: {geojson['properties']['telemetry']['spray_rate_avg']})")
    
    print(f"\n🌍 Visualizar: https://geojson.io")
    print(f"🗺️ Google Maps: https://www.google.com/maps/@{geojson['properties']['gps']['center_lat']},{geojson['properties']['gps']['center_lon']},17z")

if __name__ == "__main__":
    main()
