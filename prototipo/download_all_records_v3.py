#!/usr/bin/env python
"""
Download de TODOS os records do DJI AG - V3
Inclui TODOS os metadados da API:
- Data/hora do voo
- Altura (radar_height)
- Localização
- Drone, piloto, equipe
- Área, velocidade, spray
"""

import os
import sys
import time
import json
import struct
from datetime import datetime
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

print("=" * 70)
print(" DJI AG - DOWNLOAD COMPLETO COM METADADOS V3")
print("=" * 70)

from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")
DOWNLOAD_PATH = os.path.join(os.path.dirname(__file__), "downloads", "all_records_v3")
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# ============================================================
# FUNÇÕES DE PARSING PROTOBUF
# ============================================================
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

def create_geojson_with_metadata(binary_data, api_metadata):
    """Cria GeoJSON com dados binários + metadados da API"""
    all_values = extract_all_values(binary_data)
    
    # Pegar todas as listas brutas
    raw_lats = all_values[3]['dbl_1']
    raw_lons = all_values[3]['dbl_2']
    raw_headings = all_values[3]['dbl_3']
    
    raw_vel_x = all_values[3]['flt_1']
    raw_vel_y = all_values[3]['flt_2']
    raw_spray = all_values[3]['flt_3']
    
    # Filtrar PARES válidos de coordenadas (mantendo sincronização)
    valid_points = []
    num_raw = min(len(raw_lats), len(raw_lons))
    
    for i in range(num_raw):
        lat = raw_lats[i]
        lon = raw_lons[i]
        # Validar AMBAS coordenadas juntas
        if -35 < lat < -5 and -75 < lon < -35:
            point = {
                'lat': lat,
                'lon': lon,
                'heading': raw_headings[i] if i < len(raw_headings) and -180 <= raw_headings[i] <= 180 else None,
                'vel_x': raw_vel_x[i] if i < len(raw_vel_x) and -30 < raw_vel_x[i] < 30 else None,
                'vel_y': raw_vel_y[i] if i < len(raw_vel_y) and -30 < raw_vel_y[i] < 30 else None,
                'spray': raw_spray[i] if i < len(raw_spray) and 0 < raw_spray[i] < 50 else None,
            }
            valid_points.append(point)
    
    num_points = len(valid_points)
    
    if num_points == 0:
        return None
    
    # Extrair listas filtradas
    latitudes = [p['lat'] for p in valid_points]
    longitudes = [p['lon'] for p in valid_points]
    headings = [p['heading'] for p in valid_points if p['heading'] is not None]
    vel_x = [p['vel_x'] for p in valid_points if p['vel_x'] is not None]
    vel_y = [p['vel_y'] for p in valid_points if p['vel_y'] is not None]
    spray_values = [p['spray'] for p in valid_points if p['spray'] is not None]
    
    # Calcular estatísticas de telemetria
    avg_heading = sum(headings) / len(headings) if headings else 0
    avg_spray = sum(spray_values) / len(spray_values) if spray_values else 0
    speeds = []
    for p in valid_points:
        if p['vel_x'] is not None and p['vel_y'] is not None:
            speeds.append((p['vel_x']**2 + p['vel_y']**2)**0.5)
    avg_speed = sum(speeds) / len(speeds) if speeds else 0
    max_speed = max(speeds) if speeds else 0
    
    # Converter timestamps
    start_ts = api_metadata.get('start_timestamp')
    end_ts = api_metadata.get('end_timestamp')
    
    start_datetime = datetime.fromtimestamp(start_ts).isoformat() if start_ts else None
    end_datetime = datetime.fromtimestamp(end_ts).isoformat() if end_ts else None
    duration_seconds = (end_ts - start_ts) if (start_ts and end_ts) else None
    duration_minutes = round(duration_seconds / 60, 1) if duration_seconds else None
    
    # Criar features individuais para cada ponto (com propriedades de telemetria)
    point_features = []
    for i, p in enumerate(valid_points):
        properties = {
            "index": i,
            "latitude": p['lat'],
            "longitude": p['lon'],
        }
        
        if p['heading'] is not None:
            properties["heading"] = round(p['heading'], 2)
        if p['vel_x'] is not None:
            properties["velocity_x"] = round(p['vel_x'], 2)
        if p['vel_y'] is not None:
            properties["velocity_y"] = round(p['vel_y'], 2)
        if p['spray'] is not None:
            properties["spray_rate"] = round(p['spray'], 2)
        
        # Calcular velocidade total
        if p['vel_x'] is not None and p['vel_y'] is not None:
            speed = (p['vel_x']**2 + p['vel_y']**2)**0.5
            properties["speed_ms"] = round(speed, 2)
        
        point_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p['lon'], p['lat']]
            },
            "properties": properties
        })
    
    # Criar feature da rota (LineString)
    route_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[longitudes[i], latitudes[i]] for i in range(num_points)]
        },
        "properties": {
            "type": "flight_path",
            "total_points": num_points
        }
    }
    
    # GeoJSON completo com TODOS os metadados
    geojson = {
        "type": "FeatureCollection",
        "name": f"DJI AG Flight {api_metadata.get('id')}",
        "properties": {
            # Identificação
            "flight_record_number": api_metadata.get('id'),
            "serial_number": api_metadata.get('serial_number'),
            "hardware_id": api_metadata.get('hardware_id'),
            
            # Data e hora
            "date": api_metadata.get('create_date'),
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "duration_seconds": duration_seconds,
            "duration_minutes": duration_minutes,
            
            # Localização
            "location": api_metadata.get('location'),
            
            # Equipamento
            "drone_type": api_metadata.get('drone_type'),
            "nickname": api_metadata.get('nickname'),
            "app_version": api_metadata.get('app_version'),
            "nozzle_type": api_metadata.get('nozzle_type'),
            
            # Operador
            "pilot_name": api_metadata.get('flyer_name'),
            "team_name": api_metadata.get('team_name'),
            
            # Configurações do voo
            "flight_height_m": api_metadata.get('radar_height'),
            "max_radar_height_m": api_metadata.get('max_radar_height'),
            "work_speed_ms": api_metadata.get('work_speed'),
            "max_flight_speed_ms": api_metadata.get('max_flight_speed'),
            "spray_width_m": api_metadata.get('spray_width'),
            
            # Área e produção
            "work_area_m2": api_metadata.get('new_work_area'),
            "work_area_ha": round(api_metadata.get('new_work_area', 0) / 10000, 2),
            "spray_usage_ml": api_metadata.get('spray_usage'),
            "spray_usage_L": round(api_metadata.get('spray_usage', 0) / 1000, 2),
            "min_flow_speed_per_mu": api_metadata.get('min_flow_speed_per_mu'),
            
            # GPS
            "gps": {
                "total_points": num_points,
                "lat_min": min(latitudes),
                "lat_max": max(latitudes),
                "lon_min": min(longitudes),
                "lon_max": max(longitudes),
                "center_lat": (min(latitudes) + max(latitudes)) / 2,
                "center_lon": (min(longitudes) + max(longitudes)) / 2,
            },
            
            # Telemetria calculada
            "telemetry": {
                "heading_avg": round(avg_heading, 2),
                "heading_min": round(min(headings), 2) if headings else None,
                "heading_max": round(max(headings), 2) if headings else None,
                "speed_avg_ms": round(avg_speed, 2),
                "speed_max_ms": round(max_speed, 2),
                "spray_rate_avg": round(avg_spray, 2),
                "spray_rate_min": round(min(spray_values), 2) if spray_values else None,
                "spray_rate_max": round(max(spray_values), 2) if spray_values else None,
                "velocity_x_range": [round(min(vel_x), 2), round(max(vel_x), 2)] if vel_x else None,
                "velocity_y_range": [round(min(vel_y), 2), round(max(vel_y), 2)] if vel_y else None,
            },
            
            # Modo de operação
            "manual_mode": api_metadata.get('manual_mode'),
            "use_rtk": api_metadata.get('use_rtk_flag') == 1,
        },
        "features": [route_feature] + point_features  # LineString + todos os pontos individuais
    }
    
    return geojson

# ============================================================
# MAIN
# ============================================================
with sync_playwright() as p:
    
    print("🚀 Iniciando browser...")
    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        slow_mo=50,
        viewport={"width": 1400, "height": 900},
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    
    # ============================================================
    # COLETAR LISTA DE RECORD IDS
    # ============================================================
    print("\n📋 Coletando lista de records...")
    
    page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
    time.sleep(3)
    
    # Clicar em List
    try:
        list_btn = page.locator("button:has-text('List'), span:has-text('List')").first
        list_btn.click()
        time.sleep(3)
    except:
        pass
    
    page.wait_for_load_state("networkidle")
    
    # Coletar IDs
    record_ids = page.evaluate("""
        () => {
            const ids = [];
            document.querySelectorAll('.ant-table-row').forEach(row => {
                const key = row.getAttribute('data-row-key');
                if (key && !key.startsWith('17')) ids.push(key);  // Ignorar IDs de grupo
            });
            return ids;
        }
    """)
    
    print(f"   📊 Records encontrados: {len(record_ids)}")
    
    # ============================================================
    # BAIXAR CADA RECORD COM METADADOS COMPLETOS
    # ============================================================
    downloaded = []
    errors = []
    
    for idx, record_id in enumerate(record_ids):
        print(f"\n{'='*60}")
        print(f"📦 RECORD {idx + 1}/{len(record_ids)}: {record_id}")
        print(f"{'='*60}")
        
        record_folder = os.path.join(DOWNLOAD_PATH, f"record_{record_id}")
        geojson_file = os.path.join(record_folder, "mission.geojson")
        
        # Pular se já existe
        if os.path.exists(geojson_file):
            print(f"   ✅ Já existe, pulando...")
            with open(geojson_file) as f:
                existing = json.load(f)
                downloaded.append({
                    'id': record_id,
                    'points': existing.get('properties', {}).get('gps', {}).get('total_points', 0)
                })
            continue
        
        os.makedirs(record_folder, exist_ok=True)
        
        try:
            record_page = context.new_page()
            
            # Capturar respostas (usando lista como container mutável)
            api_metadata = [{}]  # Lista para permitir mutação dentro da closure
            flight_data = []
            
            def capture_response(response):
                try:
                    url = response.url
                    content_type = response.headers.get('content-type', '')
                    
                    # Capturar metadados JSON
                    if 'json' in content_type:
                        if f'/flight_records/{record_id}' in url and '/aggr' not in url:
                            data = response.json()
                            if data.get('data'):
                                api_metadata[0] = data['data']
                                print(f"   📋 Metadados capturados")
                    
                    # Capturar dados binários
                    if 'octet-stream' in content_type:
                        if 'flight_datas' in url or 'objects/airline' in url:
                            body = response.body()
                            if len(body) > 10000:
                                flight_data.append({
                                    'url': url,
                                    'size': len(body),
                                    'data': body
                                })
                                print(f"   📥 Dados: {len(body):,} bytes")
                except:
                    pass
            
            record_page.on("response", capture_response)
            
            # Navegar
            record_url = f"https://www.djiag.com/record/{record_id}"
            print(f"   🔗 {record_url}")
            
            record_page.goto(record_url, timeout=90000, wait_until="networkidle")
            time.sleep(8)
            
            # Screenshot
            record_page.screenshot(path=os.path.join(record_folder, "screenshot.png"))
            
            # Processar dados
            if flight_data and api_metadata[0]:
                largest = max(flight_data, key=lambda x: x['size'])
                
                # Salvar binário
                with open(os.path.join(record_folder, "route_data.bin"), 'wb') as f:
                    f.write(largest['data'])
                
                # Salvar metadados brutos
                with open(os.path.join(record_folder, "api_metadata.json"), 'w', encoding='utf-8') as f:
                    json.dump(api_metadata[0], f, indent=2, ensure_ascii=False)
                
                # Criar GeoJSON com tudo
                geojson = create_geojson_with_metadata(largest['data'], api_metadata[0])
                
                if geojson:
                    with open(geojson_file, 'w', encoding='utf-8') as f:
                        json.dump(geojson, f, indent=2, ensure_ascii=False)
                    
                    props = geojson['properties']
                    print(f"   ✅ GeoJSON salvo!")
                    print(f"   📅 Data: {props.get('date')}")
                    print(f"   ⏱️ Duração: {props.get('duration_minutes')} min")
                    print(f"   🏔️ Altura: {props.get('flight_height_m')}m")
                    print(f"   📍 Área: {props.get('work_area_ha')} ha")
                    print(f"   🚁 Drone: {props.get('drone_type')} ({props.get('nickname')})")
                    print(f"   📊 GPS: {props.get('gps', {}).get('total_points')} pontos")
                    
                    downloaded.append({
                        'id': record_id,
                        'date': props.get('date'),
                        'drone': props.get('drone_type'),
                        'area_ha': props.get('work_area_ha'),
                        'duration_min': props.get('duration_minutes'),
                        'height_m': props.get('flight_height_m'),
                        'points': props.get('gps', {}).get('total_points')
                    })
                else:
                    print(f"   ⚠️ Sem pontos GPS válidos")
                    errors.append(record_id)
            else:
                print(f"   ⚠️ Dados incompletos (meta={bool(api_metadata[0])}, data={len(flight_data)})")
                errors.append(record_id)
            
            record_page.close()
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            errors.append(record_id)
            while len(context.pages) > 1:
                try:
                    context.pages[-1].close()
                except:
                    pass
    
    # ============================================================
    # RESUMO
    # ============================================================
    print(f"\n{'='*70}")
    print("📊 RESUMO DO DOWNLOAD")
    print(f"{'='*70}")
    print(f"   Total records: {len(record_ids)}")
    print(f"   ✅ Baixados: {len(downloaded)}")
    print(f"   ❌ Erros: {len(errors)}")
    
    if downloaded:
        total_points = sum(d.get('points', 0) for d in downloaded)
        total_area = sum(d.get('area_ha', 0) or 0 for d in downloaded)
        print(f"   📍 Total pontos GPS: {total_points:,}")
        print(f"   🌾 Total área: {total_area:.2f} ha")
    
    # Salvar índice
    index_data = {
        'date': datetime.now().isoformat(),
        'total': len(record_ids),
        'downloaded': len(downloaded),
        'records': downloaded,
        'errors': errors,
    }
    
    with open(os.path.join(DOWNLOAD_PATH, "index.json"), 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Dados salvos em: {DOWNLOAD_PATH}")
    
    context.close()
    print("\n✅ Concluído!")
