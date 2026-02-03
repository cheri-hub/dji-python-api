"""
Extração COMPLETA de dados de voo DJI AG - versão final
Inclui: GPS, Altitude, Heading, Gimbal, Parâmetros de missão
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
    """Extrai todos os valores organizados por profundidade e campo"""
    
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
                
                if wire_type == 0:  # varint
                    val, pos = decode_varint(data, pos)
                    if val < 1e15:
                        all_values[depth][f'int_{field}'].append(val)
                        
                elif wire_type == 1:  # double
                    if pos + 8 <= len(data):
                        val = struct.unpack('<d', data[pos:pos+8])[0]
                        if -1e10 < val < 1e10:
                            all_values[depth][f'dbl_{field}'].append(val)
                    pos += 8
                    
                elif wire_type == 2:  # submensagem
                    length, pos = decode_varint(data, pos)
                    if length and pos + length <= len(data):
                        parse_recursive(data[pos:pos+length], depth + 1)
                        pos += length
                    else:
                        break
                        
                elif wire_type == 5:  # float
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
    
    print(f"\n{'='*70}")
    print("🚁 EXTRAÇÃO COMPLETA DE DADOS DE VOO DJI AG")
    print(f"{'='*70}\n")
    
    with open(route_file, 'rb') as f:
        data = f.read()
    
    print(f"📁 Arquivo: {os.path.basename(route_file)}")
    print(f"📊 Tamanho: {len(data):,} bytes")
    
    all_values = extract_all_values(data)
    
    # =========================================================================
    # COORDENADAS GPS (Depth 3, Fields 1 e 2)
    # =========================================================================
    latitudes = [v for v in all_values[3]['dbl_1'] if -30 < v < -20]
    longitudes = [v for v in all_values[3]['dbl_2'] if -55 < v < -40]
    headings = all_values[3]['dbl_3']
    
    print(f"\n{'='*70}")
    print("📍 COORDENADAS GPS")
    print(f"{'='*70}")
    print(f"   Pontos de GPS: {len(latitudes)}")
    print(f"   Latitude:  {min(latitudes):.6f} a {max(latitudes):.6f}")
    print(f"   Longitude: {min(longitudes):.6f} a {max(longitudes):.6f}")
    
    # =========================================================================
    # HEADING/DIREÇÃO (Depth 3, Field 3)
    # =========================================================================
    print(f"\n{'='*70}")
    print("🧭 HEADING (DIREÇÃO DO DRONE)")
    print(f"{'='*70}")
    valid_headings = [h for h in headings if -180 <= h <= 180]
    print(f"   Pontos: {len(valid_headings)}")
    print(f"   Range: {min(valid_headings):.1f}° a {max(valid_headings):.1f}°")
    print(f"   Média: {sum(valid_headings)/len(valid_headings):.1f}°")
    
    # =========================================================================
    # GIMBAL ANGLES (Depth 4, Fields 6 e 7)
    # =========================================================================
    print(f"\n{'='*70}")
    print("📷 ÂNGULOS DE GIMBAL")
    print(f"{'='*70}")
    
    gimbal_angles_6 = [v for v in all_values[4]['flt_6'] if 0 <= v <= 360]
    gimbal_angles_7 = [v for v in all_values[4]['flt_7'] if 0 <= v <= 360]
    
    print(f"   Gimbal Field 6: {len(gimbal_angles_6)} pontos")
    unique_6 = sorted(set(round(v) for v in gimbal_angles_6))
    print(f"   Valores: {unique_6}")
    
    print(f"   Gimbal Field 7: {len(gimbal_angles_7)} pontos")
    unique_7 = sorted(set(round(v) for v in gimbal_angles_7))
    print(f"   Valores: {unique_7}")
    
    # =========================================================================
    # ALTITUDE (Depth 4, Field 7 - valores discretos)
    # =========================================================================
    print(f"\n{'='*70}")
    print("🏔️ ALTITUDE DE VOO")
    print(f"{'='*70}")
    
    # Os valores 22.5, 45.0, 67.5, 90.0 parecem ser relacionados a ângulos, não altitude
    # Vamos procurar altitude em outros campos
    
    # Depth 3, int_5 tem valores de 1-99 - pode ser porcentagem ou velocidade relativa
    alt_candidates = all_values[3]['int_5']
    print(f"   Possíveis valores de altitude/velocidade (Depth 3, int_5): {len(alt_candidates)} pontos")
    print(f"   Range: {min(alt_candidates)} a {max(alt_candidates)}")
    
    # =========================================================================
    # PARÂMETROS DE MISSÃO (Valores constantes)
    # =========================================================================
    print(f"\n{'='*70}")
    print("⚙️ PARÂMETROS DE MISSÃO (valores constantes)")
    print(f"{'='*70}")
    
    # Depth 2, flt_39 = 100.0 (provavelmente bateria ou percentual)
    battery = all_values[2]['flt_39']
    if battery:
        print(f"   Bateria/Percentual (flt_39): {battery[0]}%")
    
    # Depth 2, int_10 = 10 
    int_10 = all_values[2]['int_10']
    if int_10:
        print(f"   Parâmetro int_10: {int_10[0]} (possível TASK SPEED em m/s)")
    
    # Depth 2, int_36 = 10
    int_36 = all_values[2]['int_36']
    if int_36:
        print(f"   Parâmetro int_36: {int_36[0]} (possível parâmetro relacionado)")
    
    # Depth 3, int_6 = 29
    int_6_d3 = all_values[3]['int_6']
    if int_6_d3:
        unique = set(int_6_d3)
        print(f"   Parâmetro int_6 (depth 3): {sorted(unique)}")
    
    # Depth 3, int_7 = 10
    int_7_d3 = all_values[3]['int_7']
    if int_7_d3:
        unique = set(int_7_d3)
        print(f"   Parâmetro int_7 (depth 3): {sorted(unique)} (possível ROUTE SPACING em dm ou SPEED)")
    
    # Depth 2, int_23 = 303
    int_23 = all_values[2]['int_23']
    if int_23:
        print(f"   Código de missão int_23: {int_23[0]}")
    
    # =========================================================================
    # ANÁLISE DE SPRAY FLOW RATE
    # =========================================================================
    print(f"\n{'='*70}")
    print("💧 ANÁLISE DE SPRAY/FLOW RATE")
    print(f"{'='*70}")
    
    # Depth 3, flt_3 tem valores de 0.5 a 10+
    spray_values = [v for v in all_values[3]['flt_3'] if 0 < v < 20]
    if spray_values:
        unique_spray = sorted(set(round(v, 1) for v in spray_values))
        print(f"   Flow Rate (flt_3): {len(spray_values)} pontos")
        print(f"   Valores: {unique_spray[:15]}...")
        print(f"   Range: {min(spray_values):.2f} a {max(spray_values):.2f}")
        avg_spray = sum(spray_values) / len(spray_values)
        print(f"   Média: {avg_spray:.2f}")
    
    # =========================================================================
    # DADOS DE VELOCIDADE
    # =========================================================================
    print(f"\n{'='*70}")
    print("🚀 ANÁLISE DE VELOCIDADE")
    print(f"{'='*70}")
    
    # Depth 3, flt_1 e flt_2 - parecem ser velocidades em X e Y
    vel_x = [v for v in all_values[3]['flt_1'] if -15 < v < 15]
    vel_y = [v for v in all_values[3]['flt_2'] if -15 < v < 15]
    
    if vel_x:
        print(f"   Velocidade X (flt_1): {len(vel_x)} pontos")
        print(f"   Range: {min(vel_x):.2f} a {max(vel_x):.2f} m/s")
    
    if vel_y:
        print(f"   Velocidade Y (flt_2): {len(vel_y)} pontos")
        print(f"   Range: {min(vel_y):.2f} a {max(vel_y):.2f} m/s")
    
    # =========================================================================
    # RESUMO DA MISSÃO
    # =========================================================================
    print(f"\n{'='*70}")
    print("📋 RESUMO DA MISSÃO")
    print(f"{'='*70}")
    
    mission_summary = {
        'gps': {
            'total_points': len(latitudes),
            'lat_min': min(latitudes),
            'lat_max': max(latitudes),
            'lon_min': min(longitudes),
            'lon_max': max(longitudes),
            'center_lat': (min(latitudes) + max(latitudes)) / 2,
            'center_lon': (min(longitudes) + max(longitudes)) / 2,
        },
        'heading': {
            'min': min(valid_headings),
            'max': max(valid_headings),
            'avg': sum(valid_headings) / len(valid_headings),
        },
        'gimbal_angles': unique_7,
        'parameters': {
            'battery_percent': battery[0] if battery else None,
            'speed_or_spacing': int_10[0] if int_10 else None,
            'mission_code': int_23[0] if int_23 else None,
        },
        'spray': {
            'min': min(spray_values) if spray_values else None,
            'max': max(spray_values) if spray_values else None,
            'avg': sum(spray_values) / len(spray_values) if spray_values else None,
        },
        'velocity': {
            'x_range': [min(vel_x), max(vel_x)] if vel_x else None,
            'y_range': [min(vel_y), max(vel_y)] if vel_y else None,
        }
    }
    
    print(f"\n   📍 Total pontos GPS: {mission_summary['gps']['total_points']}")
    print(f"   📍 Centro: {mission_summary['gps']['center_lat']:.6f}, {mission_summary['gps']['center_lon']:.6f}")
    print(f"   🧭 Heading médio: {mission_summary['heading']['avg']:.1f}°")
    print(f"   📷 Ângulos gimbal: {mission_summary['gimbal_angles']}")
    print(f"   🔋 Bateria: {mission_summary['parameters']['battery_percent']}%")
    print(f"   ⚡ Velocidade/Spacing: {mission_summary['parameters']['speed_or_spacing']}")
    print(f"   💧 Flow Rate médio: {mission_summary['spray']['avg']:.2f}" if mission_summary['spray']['avg'] else "")
    
    # =========================================================================
    # CRIAR TELEMETRIA COMPLETA
    # =========================================================================
    print(f"\n{'='*70}")
    print("📦 EXPORTANDO TELEMETRIA COMPLETA")
    print(f"{'='*70}")
    
    # Criar frames de telemetria
    num_frames = min(len(latitudes), len(longitudes), len(valid_headings))
    
    telemetry = []
    for i in range(num_frames):
        frame = {
            'index': i,
            'latitude': latitudes[i],
            'longitude': longitudes[i],
            'heading': valid_headings[i] if i < len(valid_headings) else None,
        }
        
        # Adicionar velocidades se disponíveis
        if i < len(vel_x):
            frame['velocity_x'] = vel_x[i]
        if i < len(vel_y):
            frame['velocity_y'] = vel_y[i]
        
        # Adicionar spray rate se disponível
        if i < len(spray_values):
            frame['spray_rate'] = spray_values[i]
            
        telemetry.append(frame)
    
    # Salvar JSON completo
    output = {
        'mission_summary': mission_summary,
        'raw_parameters': {
            'depth2_int10': int_10[0] if int_10 else None,
            'depth2_int23': int_23[0] if int_23 else None,
            'depth2_int36': int_36[0] if int_36 else None,
            'depth3_int6': list(set(int_6_d3))[:5] if int_6_d3 else None,
            'depth3_int7': list(set(int_7_d3))[:5] if int_7_d3 else None,
        },
        'telemetry_sample': telemetry[:50],  # Primeiros 50 frames
        'total_frames': len(telemetry)
    }
    
    output_path = os.path.join(records_path, "mission_data_complete.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Dados completos salvos em: {output_path}")
    
    # Criar GeoJSON enriquecido
    geojson = {
        "type": "FeatureCollection",
        "properties": mission_summary,
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lat, lon in zip(latitudes, longitudes)]
            },
            "properties": {
                "name": "DJI AG Flight Path",
                "points": len(latitudes),
                "avg_heading": mission_summary['heading']['avg'],
            }
        }]
    }
    
    geojson_path = os.path.join(records_path, "mission_route.geojson")
    with open(geojson_path, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✅ GeoJSON salvo em: {geojson_path}")
    
    # Google Maps link
    center_lat = mission_summary['gps']['center_lat']
    center_lon = mission_summary['gps']['center_lon']
    print(f"\n🌍 Google Maps: https://www.google.com/maps/@{center_lat},{center_lon},17z")
    print(f"🗺️ Visualizar GeoJSON: https://geojson.io")

if __name__ == "__main__":
    main()
