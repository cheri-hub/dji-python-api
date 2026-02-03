#!/usr/bin/env python
"""
Download de TODOS os records do DJI AG
- Faz login (se necessário)
- Clica no botão "List" para listar todos
- Itera por cada record, clicando no Playback
- Captura dados e salva GeoJSON de cada um
"""

import os
import sys
import time
import json
import struct
from datetime import datetime
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

# Carregar .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

USERNAME = os.environ.get("DJI_USERNAME", "")
PASSWORD = os.environ.get("DJI_PASSWORD", "")

print("=" * 60)
print(" DJI AG - DOWNLOAD DE TODOS OS RECORDS")
print("=" * 60)

from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")
DOWNLOAD_PATH = os.path.join(os.path.dirname(__file__), "downloads", "all_records")
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

def create_geojson(data, flight_record_number):
    """Cria GeoJSON a partir dos dados binários"""
    all_values = extract_all_values(data)
    
    latitudes = [v for v in all_values[3]['dbl_1'] if -60 < v < 10]
    longitudes = [v for v in all_values[3]['dbl_2'] if -80 < v < -30]
    headings = [h for h in all_values[3]['dbl_3'] if -180 <= h <= 180]
    
    vel_x = [v for v in all_values[3]['flt_1'] if -30 < v < 30]
    vel_y = [v for v in all_values[3]['flt_2'] if -30 < v < 30]
    spray_values = [v for v in all_values[3]['flt_3'] if 0 < v < 50]
    
    battery = all_values[2]['flt_39'][0] if all_values[2]['flt_39'] else None
    task_speed = all_values[2]['int_10'][0] if all_values[2]['int_10'] else None
    route_spacing = all_values[3]['int_7'][0] if all_values[3]['int_7'] else None
    mission_code = all_values[2]['int_23'][0] if all_values[2]['int_23'] else None
    
    num_points = min(len(latitudes), len(longitudes))
    
    if num_points == 0:
        return None
    
    # Criar features de pontos
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
        if i < len(vel_x) and i < len(vel_y):
            speed = (vel_x[i]**2 + vel_y[i]**2)**0.5
            properties["speed_ms"] = round(speed, 2)
        
        point_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [longitudes[i], latitudes[i]]},
            "properties": properties
        })
    
    route_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[longitudes[i], latitudes[i]] for i in range(num_points)]
        },
        "properties": {"type": "flight_path", "total_points": num_points}
    }
    
    # Estatísticas
    avg_heading = sum(headings) / len(headings) if headings else 0
    avg_spray = sum(spray_values) / len(spray_values) if spray_values else 0
    speeds = [(vel_x[i]**2 + vel_y[i]**2)**0.5 for i in range(min(len(vel_x), len(vel_y)))]
    avg_speed = sum(speeds) / len(speeds) if speeds else 0
    
    geojson = {
        "type": "FeatureCollection",
        "name": f"DJI AG Flight {flight_record_number}",
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
                "speed_avg_ms": round(avg_speed, 2),
                "spray_rate_avg": round(avg_spray, 2),
            }
        },
        "features": [route_feature] + point_features
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
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1400, "height": 900},
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    
    # ============================================================
    # ACESSAR PÁGINA DE RECORDS
    # ============================================================
    print("\n📍 Acessando https://www.djiag.com/br/records ...")
    page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
    time.sleep(3)
    
    current_url = page.url
    print(f"   URL: {current_url}")
    
    # Login se necessário
    if "/login" in current_url:
        print("\n🔐 Fazendo login...")
        
        try:
            checkbox = page.locator("input[type='checkbox']").first
            if checkbox:
                checkbox.click()
                time.sleep(1)
        except:
            pass
        
        try:
            dji_btn = page.locator("button:has-text('DJI'), a:has-text('DJI')").first
            dji_btn.click()
            time.sleep(3)
        except:
            pass
        
        # Esperar página de login DJI
        if "account.dji.com" in page.url:
            page.locator("input[name='username'], input[type='email']").fill(USERNAME)
            page.locator("input[name='password'], input[type='password']").fill(PASSWORD)
            page.locator("button[type='submit'], button:has-text('Log')").click()
            time.sleep(5)
        
        page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
        time.sleep(3)
    
    # ============================================================
    # CLICAR NO BOTÃO LIST
    # ============================================================
    print("\n📋 Clicando no botão 'List'...")
    
    try:
        list_btn = page.locator("button:has-text('List'), span:has-text('List')").first
        list_btn.click()
        time.sleep(3)
        print("   ✅ Botão List clicado")
    except Exception as e:
        print(f"   ⚠️ Erro ao clicar em List: {e}")
    
    # Esperar lista carregar
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(2)
    
    # ============================================================
    # CONTAR RECORDS NA LISTA
    # ============================================================
    rows = page.locator('.ant-table-row').all()
    total_records = len(rows)
    print(f"\n📊 Total de records na lista: {total_records}")
    
    if total_records == 0:
        print("❌ Nenhum record encontrado!")
        context.close()
        sys.exit(1)
    
    # ============================================================
    # ITERAR POR CADA RECORD
    # ============================================================
    downloaded = []
    errors = []
    
    for record_index in range(total_records):
        print(f"\n{'='*60}")
        print(f"📦 RECORD {record_index + 1}/{total_records}")
        print(f"{'='*60}")
        
        try:
            # Re-localizar as linhas (podem ter mudado após navegação)
            rows = page.locator('.ant-table-row').all()
            
            if record_index >= len(rows):
                print(f"   ⚠️ Linha {record_index} não encontrada, pulando...")
                continue
            
            row = rows[record_index]
            
            # Pegar última célula (Operation)
            cells = row.locator('td').all()
            if not cells:
                print(f"   ⚠️ Sem células na linha, pulando...")
                continue
            
            last_cell = cells[-1]
            
            # Procurar ícone de Playback (segundo ícone)
            icons = last_cell.locator('span.smart-ui-icon').all()
            if not icons:
                icons = last_cell.locator('span').all()
            
            if len(icons) < 2:
                print(f"   ⚠️ Ícones insuficientes ({len(icons)}), pulando...")
                continue
            
            playback_btn = icons[1]  # Segundo ícone = Playback
            
            # Clicar para abrir em nova aba
            pages_before = len(context.pages)
            playback_btn.click(modifiers=["Control"])
            time.sleep(3)
            
            pages_after = len(context.pages)
            
            if pages_after <= pages_before:
                print(f"   ⚠️ Nova aba não abriu, tentando clique normal...")
                playback_btn.click()
                time.sleep(3)
                pages_after = len(context.pages)
            
            if pages_after <= pages_before:
                print(f"   ❌ Não conseguiu abrir o record")
                errors.append(record_index)
                continue
            
            # Nova aba aberta
            new_page = context.pages[-1]
            new_page.wait_for_load_state("networkidle", timeout=60000)
            record_url = new_page.url
            
            # Extrair Flight Record Number da URL
            flight_record_number = record_url.split('/')[-1].split('?')[0]
            print(f"   📍 Flight Record: {flight_record_number}")
            print(f"   🔗 URL: {record_url}")
            
            # Capturar requests de dados
            flight_data = []
            
            def capture_response(response):
                if 'flight_datas' in response.url or 'objects/airline' in response.url:
                    try:
                        if 'octet-stream' in response.headers.get('content-type', ''):
                            body = response.body()
                            if len(body) > 10000:  # Dados significativos
                                flight_data.append({
                                    'url': response.url,
                                    'size': len(body),
                                    'data': body
                                })
                    except:
                        pass
            
            new_page.on("response", capture_response)
            
            # Esperar carregar dados
            time.sleep(5)
            
            # Criar pasta para este record
            record_folder = os.path.join(DOWNLOAD_PATH, f"record_{flight_record_number}")
            os.makedirs(record_folder, exist_ok=True)
            
            # Salvar screenshot
            screenshot_path = os.path.join(record_folder, "screenshot.png")
            new_page.screenshot(path=screenshot_path)
            print(f"   📸 Screenshot salvo")
            
            # Processar dados capturados
            if flight_data:
                # Usar o maior arquivo (provavelmente a rota principal)
                largest = max(flight_data, key=lambda x: x['size'])
                print(f"   📦 Dados capturados: {largest['size']:,} bytes")
                
                # Salvar binário
                bin_path = os.path.join(record_folder, "route_data.bin")
                with open(bin_path, 'wb') as f:
                    f.write(largest['data'])
                
                # Gerar GeoJSON
                geojson = create_geojson(largest['data'], flight_record_number)
                
                if geojson:
                    geojson_path = os.path.join(record_folder, "mission.geojson")
                    with open(geojson_path, 'w') as f:
                        json.dump(geojson, f, indent=2)
                    
                    points = geojson['properties']['mission']['total_points']
                    print(f"   ✅ GeoJSON salvo: {points} pontos GPS")
                    
                    downloaded.append({
                        'index': record_index,
                        'flight_record_number': flight_record_number,
                        'points': points,
                        'folder': record_folder
                    })
                else:
                    print(f"   ⚠️ Não foi possível criar GeoJSON")
                    errors.append(record_index)
            else:
                print(f"   ⚠️ Nenhum dado de voo capturado")
                errors.append(record_index)
            
            # Fechar aba do record
            new_page.close()
            
            # Pequena pausa entre records
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            errors.append(record_index)
            
            # Tentar fechar abas extras
            while len(context.pages) > 1:
                context.pages[-1].close()
    
    # ============================================================
    # RESUMO
    # ============================================================
    print(f"\n{'='*60}")
    print("📊 RESUMO DO DOWNLOAD")
    print(f"{'='*60}")
    print(f"   Total records: {total_records}")
    print(f"   ✅ Baixados: {len(downloaded)}")
    print(f"   ❌ Erros: {len(errors)}")
    
    # Salvar índice
    index_path = os.path.join(DOWNLOAD_PATH, "index.json")
    with open(index_path, 'w') as f:
        json.dump({
            'date': datetime.now().isoformat(),
            'total': total_records,
            'downloaded': downloaded,
            'errors': errors,
        }, f, indent=2)
    
    print(f"\n📁 Dados salvos em: {DOWNLOAD_PATH}")
    print(f"📋 Índice: {index_path}")
    
    context.close()
    print("\n✅ Concluído!")
