#!/usr/bin/env python
"""
Análise completa das páginas DJI AG para encontrar:
- KML / downloads disponíveis
- Altura de voo
- Data/hora
- Outras informações importantes
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
print(" ANÁLISE COMPLETA DAS PÁGINAS DJI AG")
print("=" * 70)

with sync_playwright() as p:
    
    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        slow_mo=50,
        viewport={"width": 1400, "height": 900},
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    
    # ============================================================
    # PARTE 1: ANALISAR PÁGINA DA LISTA (após clicar em List)
    # ============================================================
    print("\n📋 PARTE 1: Analisando página da lista...")
    
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
    time.sleep(2)
    
    # Capturar estrutura da tabela
    table_data = page.evaluate("""
        () => {
            const result = {
                headers: [],
                sample_rows: [],
                all_columns: [],
            };
            
            // Pegar headers da tabela
            const headers = document.querySelectorAll('.ant-table-thead th, table thead th');
            headers.forEach(h => {
                result.headers.push(h.textContent.trim());
            });
            
            // Pegar dados das primeiras linhas
            const rows = document.querySelectorAll('.ant-table-row, table tbody tr');
            rows.forEach((row, i) => {
                if (i < 3) {  // Primeiras 3 linhas
                    const cells = row.querySelectorAll('td');
                    const rowData = [];
                    cells.forEach(cell => {
                        rowData.push(cell.textContent.trim().substring(0, 100));
                    });
                    result.sample_rows.push(rowData);
                }
            });
            
            return result;
        }
    """)
    
    print("\n📊 COLUNAS DA TABELA:")
    for i, header in enumerate(table_data['headers']):
        print(f"   {i+1}. {header}")
    
    print("\n📋 DADOS DE EXEMPLO (primeiras linhas):")
    for i, row in enumerate(table_data['sample_rows']):
        print(f"\n   Linha {i+1}:")
        for j, cell in enumerate(row):
            header = table_data['headers'][j] if j < len(table_data['headers']) else f"Col {j}"
            if cell:
                print(f"      {header}: {cell}")
    
    # Procurar botões de download/KML
    download_buttons = page.evaluate("""
        () => {
            const buttons = [];
            const elements = document.querySelectorAll('button, a, [role="button"]');
            elements.forEach(el => {
                const text = el.textContent.toLowerCase();
                const href = el.getAttribute('href') || '';
                if (text.includes('download') || text.includes('kml') || 
                    text.includes('export') || text.includes('kmz') ||
                    href.includes('.kml') || href.includes('.kmz')) {
                    buttons.push({
                        tag: el.tagName,
                        text: el.textContent.trim(),
                        href: href,
                        classes: el.className
                    });
                }
            });
            return buttons;
        }
    """)
    
    print("\n🔽 BOTÕES DE DOWNLOAD ENCONTRADOS:")
    if download_buttons:
        for btn in download_buttons:
            print(f"   - {btn['text']} ({btn['tag']}) {btn['href']}")
    else:
        print("   Nenhum botão de download/KML visível na lista")
    
    # ============================================================
    # PARTE 2: ANALISAR PÁGINA DE UM RECORD ESPECÍFICO
    # ============================================================
    print("\n" + "=" * 70)
    print("📋 PARTE 2: Analisando página de um record específico...")
    print("=" * 70)
    
    # Capturar todas as requests
    captured_urls = []
    
    def capture_request(request):
        url = request.url
        if any(x in url.lower() for x in ['kml', 'kmz', 'flight', 'airline', 'record', 'download']):
            captured_urls.append({
                'url': url,
                'method': request.method,
                'type': request.resource_type
            })
    
    record_page = context.new_page()
    record_page.on("request", capture_request)
    
    # Navegar para um record
    record_id = "531405260"  # Um que funcionou
    record_url = f"https://www.djiag.com/record/{record_id}"
    print(f"\n🔗 Navegando para: {record_url}")
    
    record_page.goto(record_url, timeout=60000, wait_until="networkidle")
    time.sleep(5)
    
    # Analisar conteúdo da página
    page_content = record_page.evaluate("""
        () => {
            const result = {
                title: document.title,
                headers: [],
                info_panels: [],
                buttons: [],
                links: [],
                text_content: [],
                data_labels: [],
            };
            
            // Headers
            document.querySelectorAll('h1, h2, h3, h4').forEach(h => {
                const text = h.textContent.trim();
                if (text) result.headers.push(text);
            });
            
            // Painéis de informação (divs com dados)
            document.querySelectorAll('[class*="info"], [class*="detail"], [class*="panel"], [class*="card"], [class*="stat"]').forEach(el => {
                const text = el.textContent.trim().substring(0, 200);
                if (text && text.length > 5) {
                    result.info_panels.push(text);
                }
            });
            
            // Botões
            document.querySelectorAll('button, [role="button"]').forEach(btn => {
                const text = btn.textContent.trim();
                if (text) result.buttons.push(text);
            });
            
            // Links
            document.querySelectorAll('a[href]').forEach(a => {
                const href = a.getAttribute('href');
                const text = a.textContent.trim();
                if (href && (href.includes('download') || href.includes('kml') || 
                            href.includes('export') || href.includes('.kmz'))) {
                    result.links.push({text, href});
                }
            });
            
            // Procurar labels com dados (spans, divs com texto estruturado)
            const textNodes = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                const text = walker.currentNode.textContent.trim();
                if (text.length > 3 && text.length < 100) {
                    // Procurar por padrões de dados
                    if (text.match(/\\d+\\.?\\d*\\s*(m|km|ha|L|min|s|%|°|ft|m\\/s)/i) ||
                        text.match(/\\d{4}[-\\/]\\d{2}[-\\/]\\d{2}/) ||
                        text.match(/(height|altitude|speed|area|duration|date|time|flow|spacing)/i)) {
                        textNodes.push(text);
                    }
                }
            }
            result.text_content = [...new Set(textNodes)].slice(0, 50);
            
            // Procurar elementos com atributos de dados
            document.querySelectorAll('[class*="value"], [class*="number"], [class*="data"]').forEach(el => {
                const text = el.textContent.trim();
                if (text && text.length < 50) {
                    result.data_labels.push(text);
                }
            });
            
            return result;
        }
    """)
    
    print("\n📄 TÍTULO DA PÁGINA:")
    print(f"   {page_content['title']}")
    
    print("\n📊 HEADERS:")
    for h in page_content['headers'][:10]:
        print(f"   - {h}")
    
    print("\n🔢 DADOS/VALORES ENCONTRADOS:")
    for text in page_content['text_content'][:30]:
        print(f"   - {text}")
    
    print("\n🔘 BOTÕES NA PÁGINA:")
    for btn in list(set(page_content['buttons']))[:15]:
        print(f"   - {btn}")
    
    print("\n🔗 LINKS DE DOWNLOAD:")
    if page_content['links']:
        for link in page_content['links']:
            print(f"   - {link['text']}: {link['href']}")
    else:
        print("   Nenhum link de download/KML encontrado")
    
    # Analisar painel lateral/header com informações
    print("\n📋 ANALISANDO PAINEL DE INFORMAÇÕES DO VOO...")
    
    flight_info = record_page.evaluate("""
        () => {
            const info = {};
            
            // Procurar por padrões comuns de exibição de dados
            // Geralmente são pares label: value ou estruturas similares
            
            // Método 1: Procurar spans/divs adjacentes
            const allText = document.body.innerText;
            
            // Extrair padrões específicos
            const patterns = [
                /Flight\\s*(?:Record)?\\s*(?:Number|ID|#)?[:\\s]*([\\w-]+)/i,
                /Date[:\\s]*([\\d\\/\\-\\s:]+)/i,
                /Time[:\\s]*([\\d:]+)/i,
                /Duration[:\\s]*([\\d:hms\\s]+)/i,
                /Area[:\\s]*([\\.\\d]+\\s*(?:ha|m²|acres)?)/i,
                /Height[:\\s]*([\\.\\d]+\\s*(?:m|ft)?)/i,
                /Altitude[:\\s]*([\\.\\d]+\\s*(?:m|ft)?)/i,
                /Speed[:\\s]*([\\.\\d]+\\s*(?:m\\/s|km\\/h)?)/i,
                /Flow\\s*Rate[:\\s]*([\\.\\d]+\\s*(?:L\\/min|L\\/ha)?)/i,
                /Spacing[:\\s]*([\\.\\d]+\\s*(?:m)?)/i,
                /Distance[:\\s]*([\\.\\d]+\\s*(?:m|km)?)/i,
                /Volume[:\\s]*([\\.\\d]+\\s*(?:L)?)/i,
                /Battery[:\\s]*([\\.\\d]+\\s*%?)/i,
                /Drone[:\\s]*([\\w\\s-]+)/i,
                /Pilot[:\\s]*([\\w\\s]+)/i,
                /Status[:\\s]*(\\w+)/i,
            ];
            
            patterns.forEach(pattern => {
                const match = allText.match(pattern);
                if (match) {
                    const key = pattern.source.split('[')[0].replace(/\\\\/g, '').replace(/\\s\\*/g, ' ').trim();
                    info[key] = match[1].trim();
                }
            });
            
            return info;
        }
    """)
    
    print("\n📊 INFORMAÇÕES EXTRAÍDAS DO VOO:")
    if flight_info:
        for key, value in flight_info.items():
            print(f"   {key}: {value}")
    else:
        print("   Nenhuma informação estruturada encontrada")
    
    # Capturar screenshot para análise visual
    screenshot_path = os.path.join(os.path.dirname(__file__), "downloads", "page_analysis.png")
    record_page.screenshot(path=screenshot_path, full_page=True)
    print(f"\n📸 Screenshot salvo: {screenshot_path}")
    
    # Mostrar URLs capturadas
    print("\n🌐 URLS DE API CAPTURADAS:")
    for url_info in captured_urls[:20]:
        print(f"   [{url_info['method']}] {url_info['url'][:100]}")
    
    # Procurar especificamente por KML
    print("\n🔍 BUSCANDO LINKS/BOTÕES DE KML...")
    
    kml_elements = record_page.evaluate("""
        () => {
            const elements = [];
            
            // Buscar qualquer referência a KML
            document.querySelectorAll('*').forEach(el => {
                const text = (el.textContent || '').toLowerCase();
                const classes = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                const href = el.getAttribute('href') || '';
                const onclick = el.getAttribute('onclick') || '';
                
                if (text.includes('kml') || classes.includes('kml') || 
                    id.includes('kml') || href.includes('kml') || 
                    onclick.includes('kml')) {
                    elements.push({
                        tag: el.tagName,
                        text: el.textContent.trim().substring(0, 50),
                        classes: classes.substring(0, 50),
                        href: href
                    });
                }
            });
            
            return elements;
        }
    """)
    
    if kml_elements:
        print("   ✅ Elementos KML encontrados:")
        for el in kml_elements[:10]:
            print(f"      {el['tag']}: {el['text']}")
    else:
        print("   ❌ Nenhum elemento KML encontrado na página")
    
    # Verificar dados JSON na página
    print("\n🔍 BUSCANDO DADOS JSON EMBUTIDOS...")
    
    json_data = record_page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script');
            const jsonData = [];
            
            scripts.forEach(script => {
                const content = script.textContent;
                if (content.includes('height') || content.includes('altitude') || 
                    content.includes('flightData') || content.includes('mission')) {
                    // Tentar extrair objetos JSON
                    const matches = content.match(/\\{[^{}]*(?:height|altitude|flightData|mission)[^{}]*\\}/gi);
                    if (matches) {
                        jsonData.push(...matches.slice(0, 5));
                    }
                }
            });
            
            return jsonData;
        }
    """)
    
    if json_data:
        print("   📦 Dados JSON encontrados:")
        for data in json_data[:5]:
            print(f"      {data[:100]}...")
    
    record_page.close()
    context.close()
    
    print("\n" + "=" * 70)
    print("✅ Análise concluída!")
    print("=" * 70)
