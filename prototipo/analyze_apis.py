#!/usr/bin/env python
"""
Análise das APIs do DJI AG para extrair dados completos
"""

import os
import sys
import time
import json

sys.stdout.reconfigure(line_buffering=True)

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")

print("=" * 70)
print(" ANÁLISE DAS APIs DJI AG")
print("=" * 70)

with sync_playwright() as p:
    
    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        slow_mo=50,
        viewport={"width": 1400, "height": 900},
    )
    
    page = context.new_page()
    
    # Capturar TODAS as respostas de API
    api_responses = []
    
    def capture_response(response):
        url = response.url
        content_type = response.headers.get('content-type', '')
        
        if 'dji.com/api' in url or 'kr-ag2-api' in url:
            try:
                if 'json' in content_type:
                    body = response.json()
                    api_responses.append({
                        'url': url,
                        'type': 'json',
                        'data': body
                    })
                elif 'octet-stream' in content_type:
                    body = response.body()
                    api_responses.append({
                        'url': url,
                        'type': 'binary',
                        'size': len(body)
                    })
            except:
                pass
    
    page.on("response", capture_response)
    
    # Navegar para um record
    record_id = "531405260"
    print(f"\n🔗 Navegando para record: {record_id}")
    
    page.goto(f"https://www.djiag.com/record/{record_id}", timeout=60000, wait_until="networkidle")
    time.sleep(8)
    
    # Analisar respostas JSON
    print("\n" + "=" * 70)
    print("📊 DADOS JSON DAS APIs:")
    print("=" * 70)
    
    for resp in api_responses:
        if resp['type'] == 'json':
            print(f"\n🔗 {resp['url']}")
            print("-" * 60)
            
            data = resp['data']
            
            # Pretty print o JSON (até 3 níveis)
            def print_json(obj, indent=0, max_depth=3):
                if indent > max_depth:
                    print(" " * indent * 2 + "...")
                    return
                    
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, (dict, list)):
                            print(" " * indent * 2 + f"{key}:")
                            print_json(value, indent + 1, max_depth)
                        else:
                            val_str = str(value)[:80]
                            print(" " * indent * 2 + f"{key}: {val_str}")
                elif isinstance(obj, list):
                    print(" " * indent * 2 + f"[{len(obj)} items]")
                    if len(obj) > 0:
                        print_json(obj[0], indent + 1, max_depth)
            
            print_json(data)
    
    # Salvar JSON completo para análise
    output_path = os.path.join(os.path.dirname(__file__), "downloads", "api_responses.json")
    
    json_responses = [r for r in api_responses if r['type'] == 'json']
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_responses, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✅ Respostas JSON salvas em: {output_path}")
    
    # ============================================================
    # Analisar também a lista
    # ============================================================
    print("\n" + "=" * 70)
    print("📋 ANALISANDO API DA LISTA...")
    print("=" * 70)
    
    api_responses.clear()
    
    page2 = context.new_page()
    page2.on("response", capture_response)
    
    page2.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
    time.sleep(3)
    
    # Clicar em List
    try:
        list_btn = page2.locator("button:has-text('List'), span:has-text('List')").first
        list_btn.click()
        time.sleep(5)
    except:
        pass
    
    print("\n📊 DADOS JSON DA LISTA:")
    for resp in api_responses:
        if resp['type'] == 'json':
            print(f"\n🔗 {resp['url'][:80]}")
            data = resp['data']
            
            # Se for lista de records
            if isinstance(data, dict) and 'data' in data:
                records = data.get('data', [])
                if isinstance(records, list) and len(records) > 0:
                    print(f"   📦 {len(records)} records")
                    print(f"\n   CAMPOS DE CADA RECORD:")
                    sample = records[0] if records else {}
                    for key in sample.keys():
                        value = sample[key]
                        if isinstance(value, (str, int, float)):
                            print(f"      - {key}: {str(value)[:50]}")
                        else:
                            print(f"      - {key}: [{type(value).__name__}]")
    
    # Salvar lista completa
    list_output = os.path.join(os.path.dirname(__file__), "downloads", "list_api_responses.json")
    json_responses = [r for r in api_responses if r['type'] == 'json']
    with open(list_output, 'w', encoding='utf-8') as f:
        json.dump(json_responses, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✅ Dados da lista salvos em: {list_output}")
    
    page.close()
    page2.close()
    context.close()
    
    print("\n" + "=" * 70)
    print("✅ Análise concluída!")
    print("=" * 70)
