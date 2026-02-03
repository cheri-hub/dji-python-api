#!/usr/bin/env python
"""
Download de TODOS os records do DJI AG - V2
- Navega para cada record diretamente pela URL
- Captura os dados de voo via network
- Gera GeoJSON para cada missão
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
print(" DJI AG - DOWNLOAD DE TODOS OS RECORDS V2")
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
    
    route_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[longitudes[i], latitudes[i]] for i in range(num_points)]
        },
        "properties": {"type": "flight_path", "total_points": num_points}
    }
    
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
        "features": [route_feature]
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
    # ACESSAR PÁGINA E COLETAR LISTA DE RECORDS
    # ============================================================
    print("\n📍 Acessando https://www.djiag.com/br/records ...")
    page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
    time.sleep(3)
    
    current_url = page.url
    
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
        
        if "account.dji.com" in page.url:
            page.locator("input[name='username'], input[type='email']").fill(USERNAME)
            page.locator("input[name='password'], input[type='password']").fill(PASSWORD)
            page.locator("button[type='submit'], button:has-text('Log')").click()
            time.sleep(5)
        
        page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
        time.sleep(3)
    
    # Clicar no botão List
    print("\n📋 Clicando no botão 'List'...")
    try:
        list_btn = page.locator("button:has-text('List'), span:has-text('List')").first
        list_btn.click()
        time.sleep(3)
    except:
        pass
    
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(2)
    
    # Coletar todos os record IDs da tabela
    print("\n📋 Coletando IDs dos records...")
    
    record_ids = page.evaluate("""
        () => {
            const ids = [];
            const rows = document.querySelectorAll('.ant-table-row');
            
            rows.forEach((row, i) => {
                // Tentar pegar o data-row-key
                const rowKey = row.getAttribute('data-row-key');
                if (rowKey) {
                    ids.push(rowKey);
                } else {
                    // Tentar extrair do link/botão de playback
                    const link = row.querySelector('a[href*="/record/"]');
                    if (link) {
                        const href = link.getAttribute('href');
                        const match = href.match(/\\/record\\/(\\d+)/);
                        if (match) {
                            ids.push(match[1]);
                        }
                    }
                }
            });
            
            return ids;
        }
    """)
    
    print(f"   📊 IDs coletados: {len(record_ids)}")
    
    # Se não conseguiu coletar, tentar de outra forma
    if not record_ids:
        print("   ⚠️ Tentando coletar IDs via click nos botões...")
        
        # Coletar usando os botões de playback
        rows = page.locator('.ant-table-row').all()
        collected_ids = []
        
        for i, row in enumerate(rows):
            try:
                cells = row.locator('td').all()
                if cells:
                    last_cell = cells[-1]
                    icons = last_cell.locator('span.smart-ui-icon').all()
                    if len(icons) >= 2:
                        # Hover para ver se tem link
                        icons[1].hover()
                        time.sleep(0.2)
            except:
                pass
        
        # Buscar no index.json existente
        index_file = os.path.join(DOWNLOAD_PATH, "index.json")
        if os.path.exists(index_file):
            with open(index_file) as f:
                existing = json.load(f)
                if existing.get('errors'):
                    print(f"   📋 Usando IDs do índice anterior")
    
    # Se ainda não tem IDs, usar os que já conhecemos
    if not record_ids:
        # Extrair das pastas já criadas + lista conhecida
        record_ids = []
        for folder in os.listdir(DOWNLOAD_PATH):
            if folder.startswith('record_'):
                record_id = folder.replace('record_', '')
                if record_id.isdigit():
                    record_ids.append(record_id)
        
        # Lista conhecida do teste anterior
        known_ids = [
            "531405271", "531405260", "531405255", "531405250", "531405244",
            "531405236", "531405224", "531405208", "531405204", "531405198",
            "531405178", "531405172", "531405168", "531405159", "531405154",
            "531405148", "531405139", "531405129", "531405122", "531405117",
            "531405111", "531405103", "531405095", "531405091", "531405087",
            "531405080", "531405074", "530510390", "530510384", "530510383",
            "530510380"
        ]
        
        for id in known_ids:
            if id not in record_ids:
                record_ids.append(id)
    
    print(f"\n📊 Total de records para processar: {len(record_ids)}")
    
    # ============================================================
    # BAIXAR CADA RECORD
    # ============================================================
    downloaded = []
    errors = []
    
    for idx, record_id in enumerate(record_ids):
        print(f"\n{'='*60}")
        print(f"📦 RECORD {idx + 1}/{len(record_ids)}: {record_id}")
        print(f"{'='*60}")
        
        record_folder = os.path.join(DOWNLOAD_PATH, f"record_{record_id}")
        
        # Verificar se já foi baixado
        geojson_file = os.path.join(record_folder, "mission.geojson")
        if os.path.exists(geojson_file):
            print(f"   ✅ Já existe, pulando...")
            with open(geojson_file) as f:
                existing = json.load(f)
                downloaded.append({
                    'flight_record_number': record_id,
                    'points': existing.get('properties', {}).get('mission', {}).get('total_points', 0),
                    'folder': record_folder
                })
            continue
        
        os.makedirs(record_folder, exist_ok=True)
        
        try:
            # Criar nova página para capturar requests desde o início
            record_page = context.new_page()
            
            # Variável para armazenar dados capturados
            flight_data = []
            
            def capture_response(response):
                try:
                    content_type = response.headers.get('content-type', '')
                    if 'octet-stream' in content_type:
                        if 'flight_datas' in response.url or 'objects/airline' in response.url:
                            body = response.body()
                            if len(body) > 10000:
                                flight_data.append({
                                    'url': response.url,
                                    'size': len(body),
                                    'data': body
                                })
                                print(f"   📥 Capturado: {len(body):,} bytes")
                except Exception as e:
                    pass
            
            # Registrar handler ANTES de navegar
            record_page.on("response", capture_response)
            
            # Navegar para a página do record
            record_url = f"https://www.djiag.com/record/{record_id}"
            print(f"   🔗 Navegando para: {record_url}")
            
            record_page.goto(record_url, timeout=60000, wait_until="networkidle")
            
            # Esperar dados carregarem
            print(f"   ⏳ Aguardando dados...")
            time.sleep(8)  # Dar tempo para os dados carregarem
            
            # Screenshot
            screenshot_path = os.path.join(record_folder, "screenshot.png")
            record_page.screenshot(path=screenshot_path)
            print(f"   📸 Screenshot salvo")
            
            # Processar dados capturados
            if flight_data:
                largest = max(flight_data, key=lambda x: x['size'])
                print(f"   📦 Maior arquivo: {largest['size']:,} bytes")
                
                # Salvar binário
                bin_path = os.path.join(record_folder, "route_data.bin")
                with open(bin_path, 'wb') as f:
                    f.write(largest['data'])
                
                # Gerar GeoJSON
                geojson = create_geojson(largest['data'], record_id)
                
                if geojson and geojson['properties']['mission']['total_points'] > 0:
                    with open(geojson_file, 'w') as f:
                        json.dump(geojson, f, indent=2)
                    
                    points = geojson['properties']['mission']['total_points']
                    center = geojson['properties']['gps']
                    print(f"   ✅ GeoJSON: {points} pontos GPS")
                    print(f"   📍 Centro: {center['center_lat']:.4f}, {center['center_lon']:.4f}")
                    
                    downloaded.append({
                        'flight_record_number': record_id,
                        'points': points,
                        'folder': record_folder
                    })
                else:
                    print(f"   ⚠️ Sem pontos GPS válidos")
                    errors.append(record_id)
            else:
                print(f"   ⚠️ Nenhum dado capturado")
                errors.append(record_id)
            
            # Fechar página
            record_page.close()
            
            # Pausa entre records
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            errors.append(record_id)
            
            # Fechar páginas extras
            while len(context.pages) > 1:
                try:
                    context.pages[-1].close()
                except:
                    pass
    
    # ============================================================
    # RESUMO
    # ============================================================
    print(f"\n{'='*60}")
    print("📊 RESUMO DO DOWNLOAD")
    print(f"{'='*60}")
    print(f"   Total records: {len(record_ids)}")
    print(f"   ✅ Baixados: {len(downloaded)}")
    print(f"   ❌ Erros: {len(errors)}")
    
    if downloaded:
        total_points = sum(d['points'] for d in downloaded)
        print(f"   📍 Total pontos GPS: {total_points:,}")
    
    # Salvar índice
    index_path = os.path.join(DOWNLOAD_PATH, "index.json")
    with open(index_path, 'w') as f:
        json.dump({
            'date': datetime.now().isoformat(),
            'total': len(record_ids),
            'downloaded': len(downloaded),
            'records': downloaded,
            'errors': errors,
        }, f, indent=2)
    
    print(f"\n📁 Dados salvos em: {DOWNLOAD_PATH}")
    print(f"📋 Índice: {index_path}")
    
    context.close()
    print("\n✅ Concluído!")
