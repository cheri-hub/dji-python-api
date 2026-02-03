#!/usr/bin/env python
"""
Teste de login DJI AG seguindo o fluxo correto:
1. Acessar https://www.djiag.com/br/records
2. Se redirecionar para login: clicar "I have read..." + "Login with DJI account"
3. Preencher email/senha no account.dji.com
4. Verificar sucesso
5. Download via API usando cookies da sessão
"""

import os
import sys
import time
import json
from datetime import datetime

# Força output imediato
sys.stdout.reconfigure(line_buffering=True)

# Carregar .env manualmente
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
print(" TESTE LOGIN DJI AG - FLUXO CORRETO")
print("=" * 60)
print(f"Email: {USERNAME}")
print(f"Senha: {'*' * len(PASSWORD)}")
print()

from playwright.sync_api import sync_playwright

# Diretório para perfil persistente do browser
# Usar perfil fixo para manter sessão entre execuções
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")
os.makedirs(USER_DATA_DIR, exist_ok=True)
print(f"Perfil: {USER_DATA_DIR}")

with sync_playwright() as p:
    
    # ============================================================
    # INICIAR BROWSER
    # ============================================================
    print("🚀 Iniciando browser...")
    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        slow_mo=100,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1280, "height": 800},
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    
    # Script anti-detecção
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    
    # ============================================================
    # ETAPA 1: Acessar djiag.com/br/records
    # ============================================================
    print("\n📍 ETAPA 1: Acessando https://www.djiag.com/br/records ...")
    page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
    
    # Aguardar estabilização da página (pode redirecionar)
    time.sleep(5)
    
    # Verificar URL após carregamento completo
    current_url = page.url
    print(f"   URL após carregamento: {current_url}")
    
    # ============================================================
    # ETAPA 2: Verificar se precisa login
    # ============================================================
    print("\n📍 ETAPA 2: Verificando se precisa login...")
    
    # Se a URL contém /login, precisamos fazer login
    needs_login = "/login" in current_url
    
    if not needs_login:
        print("   ✅ Parece autenticado, verificando página...")
    else:
        print("   ⚠️ Página de login detectada. Iniciando processo de login...")
    
    # Se precisa login, executar o processo
    if needs_login:
        # Aceitar cookies se aparecer
        try:
            cookies_btn = page.locator("button:has-text('Accept'), button:has-text('Aceitar')").first
            if cookies_btn.is_visible(timeout=2000):
                cookies_btn.click()
                print("   ✅ Cookies aceitos")
                time.sleep(1)
        except:
            pass
        
        # Procurar checkbox "I have read..."
        try:
            checkbox = page.locator("input[type='checkbox']").first
            if checkbox.is_visible(timeout=5000):
                checkbox.click()
                print("   ✅ Checkbox 'I have read...' marcado")
                time.sleep(1)
        except Exception as e:
            print(f"   ℹ️ Checkbox não encontrado ou não visível")
        
        # Procurar botão "Login with DJI account"
        try:
            # Tentar vários seletores
            selectors = [
                "button:has-text('Log in with DJI')",
                "button:has-text('Login with DJI')", 
                "a:has-text('Log in with DJI')",
                "a:has-text('Login with DJI')",
                "[class*='login']",
                "button:has-text('Log in')",
                "button:has-text('Login')",
            ]
            
            clicked = False
            for selector in selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        print(f"   ✅ Botão clicado: {selector}")
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                print("   ⚠️ Nenhum botão de login encontrado")
            
            time.sleep(3)
        except Exception as e:
            print(f"   ⚠️ Erro procurando botão: {e}")
        
        current_url = page.url
        print(f"   URL após clique: {current_url}")
        
        # Aguardar página do account.dji.com carregar
        time.sleep(3)
        current_url = page.url
        print(f"   URL atual: {current_url}")
        
        # ============================================================
        # ETAPA 3: Preencher credenciais no account.dji.com
        # ============================================================
        print("\n📍 ETAPA 3: Preenchendo credenciais...")
        
        if "account.dji.com" in current_url:
            print("   📍 Estamos no account.dji.com")
            
            # Aguardar formulário de login aparecer
            time.sleep(2)
            
            # Campo de email
            try:
                email_field = page.locator("input[name='username'], input[type='email'], input[type='text']").first
                if email_field.is_visible(timeout=5000):
                    email_field.click()
                    time.sleep(0.3)
                    email_field.type(USERNAME, delay=30)
                    print("   ✅ Email preenchido")
                    time.sleep(0.5)
            except Exception as e:
                print(f"   ❌ Erro no email: {e}")
            
            # Campo de senha
            try:
                pass_field = page.locator("input[type='password']").first
                if pass_field.is_visible(timeout=3000):
                    pass_field.click()
                    time.sleep(0.3)
                    pass_field.type(PASSWORD, delay=30)
                    print("   ✅ Senha preenchida")
                    time.sleep(0.5)
            except Exception as e:
                print(f"   ❌ Erro na senha: {e}")
            
            # Clicar em Login - tentar vários seletores
            print("   🖱️ Procurando botão de login...")
            clicked = False
            
            login_selectors = [
                "button[type='submit']",
                "button:has-text('Log in')",
                "button:has-text('Login')",
                "button:has-text('Sign in')",
                ".submit-btn",
                "#login-btn",
            ]
            
            for selector in login_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        print(f"   ✅ Botão Login clicado: {selector}")
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                # Tentar pressionar Enter no campo de senha
                try:
                    pass_field = page.locator("input[type='password']").first
                    pass_field.press("Enter")
                    print("   ✅ Enter pressionado no campo de senha")
                    clicked = True
                except:
                    print("   ❌ Não foi possível clicar no botão de login")
            
            # Aguardar redirecionamento
            print("\n   ⏳ Aguardando redirecionamento...")
            print("   💡 Se aparecer CAPTCHA, complete manualmente!")
            
            for i in range(60):
                time.sleep(1)
                current_url = page.url
                if "account.dji.com/login" not in current_url and "account.dji.com/logout" not in current_url:
                    print(f"   ✅ Redirecionado para: {current_url}")
                    break
                if i % 10 == 0 and i > 0:
                    print(f"   ⏳ Aguardando... ({i}s)")
        else:
            print(f"   ⚠️ Não estamos no account.dji.com. URL: {current_url}")
    
    # ============================================================
    # ETAPA 4: Garantir que estamos em /records
    # ============================================================
    print("\n📍 ETAPA 4: Verificando se estamos em /records...")
    
    current_url = page.url
    
    # Só navegar se não estiver em /records
    if "/records" not in current_url or "/login" in current_url:
        print(f"   URL atual: {current_url}")
        print("   🔄 Navegando para /records...")
        page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
        time.sleep(3)
        current_url = page.url
    
    print(f"   URL: {current_url}")
    
    # Se ainda não está em /records, tentar novamente
    max_attempts = 3
    for attempt in range(max_attempts):
        if "/records" in current_url and "/login" not in current_url:
            break
        
        print(f"   ⚠️ Não está em /records (tentativa {attempt + 1}/{max_attempts})")
        
        # Se está em /mission ou outra página, navegar para /records
        if "/login" not in current_url:
            print("   🔄 Redirecionando para /records...")
            page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
            time.sleep(3)
            current_url = page.url
            print(f"   URL: {current_url}")
        else:
            # Ainda em login, falhou
            break
    
    final_url = page.url
    print(f"   URL final: {final_url}")
    
    if "/records" in final_url and "/login" not in final_url:
        print("\n" + "=" * 60)
        print(" ✅ LOGIN BEM-SUCEDIDO! Redirecionado para /records")
        print("=" * 60)
        
        # ============================================================
        # Capturar TODAS as requisições de API durante carregamento
        # ============================================================
        all_api_calls = []
        
        def capture_all_requests(request):
            url = request.url
            if "api" in url.lower() and "djiag.com" in url:
                all_api_calls.append({
                    "method": request.method,
                    "url": url,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                })
                print(f"   📡 API: {request.method} {url}")
        
        page.on("request", capture_all_requests)
        
        # Esperar a página carregar completamente e capturar APIs
        print("\n📊 Capturando chamadas de API...")
        time.sleep(3)
        
        # Recarregar para capturar todas as chamadas
        print("   🔄 Recarregando página para capturar APIs...")
        page.reload()
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(2)
        
        page.remove_listener("request", capture_all_requests)
        
        # Salvar APIs capturadas
        download_path = os.path.join(os.path.dirname(__file__), "downloads")
        os.makedirs(download_path, exist_ok=True)
        
        if all_api_calls:
            apis_path = os.path.join(download_path, "all_apis.json")
            with open(apis_path, "w", encoding="utf-8") as f:
                json.dump(all_api_calls, f, indent=2, ensure_ascii=False)
            print(f"\n   ✅ {len(all_api_calls)} APIs capturadas e salvas em: {apis_path}")
        
        # Salvar screenshot da página de records
        screenshot_path = os.path.join(os.path.dirname(__file__), "records_page.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"   📸 Screenshot salvo: {screenshot_path}")
        
        # Salvar HTML para análise
        html = page.content()
        html_path = os.path.join(os.path.dirname(__file__), "records_page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"   📄 HTML salvo: {html_path}")
        
        # ============================================================
        # ETAPA 5: Download via clique no botão DownloadAll
        # (API requer assinatura WebAssembly, não pode ser feita via request)
        # ============================================================
        print("\n📍 ETAPA 5: Download automático...")
        print(f"   📁 Diretório de downloads: {download_path}")
        
        # Extrair e salvar cookies para uso futuro
        print("   🍪 Extraindo cookies da sessão...")
        browser_cookies = context.cookies()
        cookies_path = os.path.join(download_path, "session_cookies.json")
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(browser_cookies, f, indent=2, ensure_ascii=False)
        print(f"   ✅ {len(browser_cookies)} cookies salvos")
        
        # Capturar API de export durante o clique
        export_apis = []
        
        def on_export_request(request):
            url = request.url
            # Capturar qualquer requisição que não seja estática
            if "djiag.com" in url and not any(x in url for x in ['.js', '.css', '.png', '.svg', '.woff']):
                export_apis.append({
                    "method": request.method,
                    "url": url,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                    "resource_type": request.resource_type,
                })
                print(f"      📡 {request.resource_type}: {request.method} {url[:80]}")
        
        page.on("request", on_export_request)
        
        # ============================================================
        # Clicar no botão "List" para mostrar a lista de records
        # ============================================================
        print("\n   🔄 Clicando no botão 'List' para mostrar a lista...")
        
        list_btn_clicked = False
        list_selectors = [
            "div[role='tab']:has-text('List')",
            ".ant-tabs-tab:has-text('List')",
            "div.ant-tabs-tab-btn:has-text('List')",
            "[class*='tab']:has-text('List')",
        ]
        
        for selector in list_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f"   ✅ Botão 'List' clicado: {selector}")
                    list_btn_clicked = True
                    time.sleep(2)  # Aguardar lista carregar
                    break
            except:
                continue
        
        if not list_btn_clicked:
            print("   ⚠️ Botão 'List' não encontrado, tentando via texto...")
            try:
                page.get_by_text("List", exact=True).click()
                print("   ✅ Botão 'List' clicado via texto")
                time.sleep(2)
            except:
                print("   ⚠️ Não foi possível clicar em 'List'")
        
        # Listar todos os botões para encontrar o de export
        print("\n   📋 Listando botões da página...")
        buttons_info = page.evaluate("""
            () => {
                const buttons = [];
                document.querySelectorAll('button, a[role="button"], [class*="btn"], [class*="button"]').forEach((btn, i) => {
                    if (i < 30) {
                        const text = btn.textContent.trim().substring(0, 50);
                        const classes = btn.className || '';
                        const hasIcon = btn.querySelector('svg') !== null;
                        buttons.push({
                            index: i,
                            text: text,
                            classes: classes.substring(0, 80),
                            tag: btn.tagName,
                            hasIcon: hasIcon,
                        });
                    }
                });
                return buttons;
            }
        """)
        
        for btn in buttons_info:
            if btn.get('text') or 'export' in btn.get('classes', '').lower() or 'download' in btn.get('classes', '').lower():
                print(f"      [{btn['index']}] {btn['tag']}: '{btn['text']}' | classes: {btn['classes'][:40]}")
        
        # Procurar botão DownloadAll especificamente
        print("\n   🖱️ Procurando botão DownloadAll...")
        
        download_btn = None
        for btn in buttons_info:
            if 'downloadall' in btn.get('text', '').lower().replace(' ', ''):
                download_btn = btn
                break
        
        if download_btn:
            print(f"   ✅ Botão encontrado: [{download_btn['index']}] '{download_btn['text']}'")
            
            # Usar expect_download para capturar o arquivo
            all_buttons = page.locator('button, a[role="button"], [class*="btn"], [class*="button"]').all()
            
            if download_btn['index'] < len(all_buttons):
                try:
                    with page.expect_download(timeout=60000) as download_info:
                        print("   🖱️ Clicando no botão...")
                        all_buttons[download_btn['index']].click()
                    
                    download = download_info.value
                    filename = download.suggested_filename
                    filepath = os.path.join(download_path, filename)
                    download.save_as(filepath)
                    print(f"\n   ✅ DOWNLOAD CONCLUÍDO!")
                    print(f"   📁 Arquivo: {filename}")
                    print(f"   📂 Caminho: {filepath}")
                    
                    # Verificar tamanho
                    file_size = os.path.getsize(filepath)
                    print(f"   📦 Tamanho: {file_size:,} bytes")
                    
                except Exception as e:
                    print(f"   ❌ Erro no download: {e}")
        else:
            print("   ⚠️ Botão DownloadAll não encontrado")
        
        page.remove_listener("request", on_export_request)
        
        # Salvar APIs de export capturadas
        if export_apis:
            export_path = os.path.join(download_path, "export_apis.json")
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_apis, f, indent=2, ensure_ascii=False)
            print(f"\n   📡 {len(export_apis)} APIs de export capturadas: {export_path}")
        
        print("\n   ✅ ETAPA 5 concluída!")
        
        # ============================================================
        # ETAPA 6: Mapear e baixar records individuais
        # ============================================================
        print("\n📍 ETAPA 6: Mapeando records individuais...")
        
        # Criar pasta para records individuais
        records_path = os.path.join(download_path, "records")
        os.makedirs(records_path, exist_ok=True)
        print(f"   📁 Pasta de records: {records_path}")
        
        # Aguardar lista carregar após o download
        time.sleep(2)
        
        # Identificar itens da lista
        print("\n   🔍 Identificando itens da lista...")
        
        list_items = page.evaluate("""
            () => {
                const items = [];
                // Procurar linhas da tabela ou itens de lista
                const selectors = [
                    'table tbody tr',
                    '.ant-table-row',
                    '[class*="list-item"]',
                    '[class*="record-item"]',
                    '[class*="task-item"]',
                ];
                
                for (const selector of selectors) {
                    const rows = document.querySelectorAll(selector);
                    if (rows.length > 0) {
                        rows.forEach((row, i) => {
                            // Procurar botão de visualização na linha
                            const viewBtn = row.querySelector('button, a, [class*="view"], [class*="detail"], svg');
                            const text = row.textContent.trim().substring(0, 100);
                            items.push({
                                index: i,
                                selector: selector,
                                text: text,
                                hasViewButton: viewBtn !== null,
                            });
                        });
                        break;
                    }
                }
                return items;
            }
        """)
        
        print(f"   📊 Encontrados {len(list_items)} itens na lista")
        
        if list_items:
            # Mostrar primeiros itens
            for item in list_items[:5]:
                print(f"      [{item['index']}] {item['text'][:60]}...")
            
            if len(list_items) > 5:
                print(f"      ... e mais {len(list_items) - 5} itens")
        
        # Mapear estrutura dos botões de visualização
        print("\n   🔍 Mapeando estrutura da lista...")
        
        # Tentar identificar a estrutura real da lista
        list_structure = page.evaluate("""
            () => {
                const result = {
                    rows: [],
                    selectors_found: [],
                };
                
                // Tentar diferentes seletores
                const selectors = [
                    '.ant-table-row',
                    'table tbody tr',
                    '[class*="list"] [class*="item"]',
                    '[class*="record"]',
                    '[class*="task-row"]',
                ];
                
                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        result.selectors_found.push({selector, count: elements.length});
                        
                        elements.forEach((el, i) => {
                            if (i < 5) {  // Apenas primeiros 5 para debug
                                const classes = typeof el.className === 'string' ? el.className : '';
                                result.rows.push({
                                    index: i,
                                    selector: selector,
                                    tagName: el.tagName,
                                    classes: classes.substring(0, 80),
                                    text: (el.textContent || '').trim().substring(0, 80),
                                    isClickable: el.onclick !== null || el.tagName === 'A' || el.style.cursor === 'pointer',
                                    childButtons: el.querySelectorAll('button, a, [role="button"]').length,
                                });
                            }
                        });
                    }
                }
                
                return result;
            }
        """)
        
        print(f"   📊 Seletores encontrados:")
        for sel in list_structure.get('selectors_found', []):
            print(f"      {sel['selector']}: {sel['count']} elementos")
        
        if list_structure.get('rows'):
            print(f"\n   📋 Estrutura das primeiras linhas:")
            for row in list_structure['rows'][:3]:
                print(f"      [{row['index']}] {row['tagName']} | botões: {row['childButtons']} | classes: {row['classes'][:40]}")
        
        # Verificar se há linhas clicáveis na tabela
        # O botão de Playback está na última coluna (Operation)
        print(f"\n   📍 Procurando botões de Playback na coluna Operation...")
        
        # Investigar estrutura detalhada das linhas
        row_structure = page.evaluate("""
            () => {
                const rows = document.querySelectorAll('.ant-table-row');
                const result = [];
                
                rows.forEach((row, i) => {
                    if (i < 3) {  // Apenas primeiras 3 linhas
                        const cells = row.querySelectorAll('td');
                        const lastCell = cells[cells.length - 1];  // Última célula (Operation)
                        
                        // Procurar todos os elementos clicáveis na última célula
                        const clickables = lastCell ? lastCell.querySelectorAll('span, button, a, svg, [role="button"]') : [];
                        const clickableInfo = [];
                        
                        clickables.forEach((el, j) => {
                            clickableInfo.push({
                                index: j,
                                tag: el.tagName,
                                classes: typeof el.className === 'string' ? el.className.substring(0, 60) : '',
                                title: el.getAttribute('title') || '',
                                ariaLabel: el.getAttribute('aria-label') || '',
                            });
                        });
                        
                        result.push({
                            rowIndex: i,
                            totalCells: cells.length,
                            lastCellClickables: clickableInfo,
                            dataRowKey: row.getAttribute('data-row-key'),
                        });
                    }
                });
                
                return result;
            }
        """)
        
        print(f"\n   📋 Estrutura da coluna Operation:")
        for row in row_structure[:2]:
            print(f"      Linha {row['rowIndex']}: {len(row['lastCellClickables'])} elementos clicáveis")
            for el in row['lastCellClickables'][:5]:
                info = f"title='{el['title']}'" if el['title'] else f"classes='{el['classes'][:30]}'"
                print(f"         [{el['index']}] {el['tag']}: {info}")
        
        # Testar clicar no botão de Playback
        print("\n   🔬 Testando abertura do primeiro record via Playback...")
        
        try:
            rows = page.locator('.ant-table-row').all()
            print(f"   📊 Linhas encontradas: {len(rows)}")
            
            if len(rows) > 1:
                # A linha 0 é geralmente o header/grupo, usar linha 1
                row_to_use = rows[1]
                
                # Pegar a última célula (Operation)
                cells = row_to_use.locator('td').all()
                print(f"   📋 Células na linha: {len(cells)}")
                
                if cells:
                    last_cell = cells[-1]
                    
                    # Procurar os spans com classe de ícone clicável
                    icons = last_cell.locator('span.smart-ui-icon').all()
                    print(f"   🔍 Ícones smart-ui-icon: {len(icons)}")
                    
                    if not icons:
                        # Tentar pegar todos os spans
                        icons = last_cell.locator('span').all()
                        print(f"   🔍 Todos os spans: {len(icons)}")
                    
                    # O botão de Playback é o segundo ícone (índice 1)
                    playback_btn = None
                    if len(icons) >= 2:
                        playback_btn = icons[1]  # Segundo ícone
                        print(f"   ✅ Usando segundo ícone como Playback")
                    elif len(icons) == 1:
                        playback_btn = icons[0]
                        print(f"   ⚠️ Apenas 1 ícone encontrado, usando ele")
                    
                    if playback_btn:
                        # Clicar com Ctrl para forçar abertura em nova aba
                        print(f"   🖱️ Clicando no botão Playback (Ctrl+Click)...")
                        
                        # Contar páginas antes do clique
                        pages_before = len(context.pages)
                        
                        # Ctrl+Click força abertura em nova aba
                        playback_btn.click(modifiers=["Control"])
                        time.sleep(3)  # Esperar abrir
                        
                        # Verificar se abriu nova aba
                        pages_after = len(context.pages)
                        print(f"   📊 Páginas antes: {pages_before}, depois: {pages_after}")
                        
                        if pages_after > pages_before:
                            # Abriu nova aba
                            new_page = context.pages[-1]
                            new_page.wait_for_load_state("networkidle", timeout=60000)
                            record_url = new_page.url
                            print(f"   ✅ Nova aba aberta: {record_url}")
                            is_new_tab = True
                        else:
                            # Tentar clique normal e esperar navegação
                            print("   ⚠️ Ctrl+Click não abriu nova aba, tentando clique normal...")
                            playback_btn.click()
                            time.sleep(3)
                            
                            pages_after = len(context.pages)
                            if pages_after > pages_before:
                                new_page = context.pages[-1]
                                new_page.wait_for_load_state("networkidle", timeout=60000)
                                record_url = new_page.url
                                print(f"   ✅ Nova aba aberta: {record_url}")
                                is_new_tab = True
                            else:
                                page.wait_for_load_state("networkidle", timeout=30000)
                                record_url = page.url
                                print(f"   ✅ Navegou para: {record_url}")
                                new_page = page
                                is_new_tab = False
                        
                        # Salvar screenshot do record
                        record_screenshot = os.path.join(records_path, "record_0_screenshot.png")
                        new_page.screenshot(path=record_screenshot, full_page=True)
                        print(f"   📸 Screenshot salvo: {record_screenshot}")
                        
                        # Procurar botão de download no record
                        print("\n   🔍 Analisando todos os elementos da página do record...")
                        
                        # Análise completa da página
                        page_analysis = new_page.evaluate("""
                            () => {
                                const result = {
                                    videos: [],
                                    iframes: [],
                                    canvas: [],
                                    links: [],
                                    buttons: [],
                                    images: [],
                                    audios: [],
                                    sources: [],
                                    divs_with_video_class: [],
                                    all_media: [],
                                };
                                
                                // Vídeos
                                document.querySelectorAll('video').forEach((el, i) => {
                                    result.videos.push({
                                        index: i,
                                        src: el.src || el.currentSrc || '',
                                        poster: el.poster || '',
                                        sources: Array.from(el.querySelectorAll('source')).map(s => s.src),
                                    });
                                });
                                
                                // Iframes
                                document.querySelectorAll('iframe').forEach((el, i) => {
                                    result.iframes.push({
                                        index: i,
                                        src: el.src || '',
                                    });
                                });
                                
                                // Canvas (pode ser onde renderiza o playback)
                                document.querySelectorAll('canvas').forEach((el, i) => {
                                    result.canvas.push({
                                        index: i,
                                        width: el.width,
                                        height: el.height,
                                        id: el.id || '',
                                        classes: typeof el.className === 'string' ? el.className : '',
                                    });
                                });
                                
                                // Links com download ou arquivos
                                document.querySelectorAll('a').forEach((el, i) => {
                                    const href = el.href || '';
                                    const text = (el.textContent || '').trim();
                                    if (href && (href.includes('download') || href.includes('.mp4') || 
                                        href.includes('.zip') || href.includes('.pdf') || 
                                        href.includes('blob:') || el.hasAttribute('download'))) {
                                        result.links.push({
                                            index: i,
                                            href: href.substring(0, 100),
                                            text: text.substring(0, 30),
                                            hasDownload: el.hasAttribute('download'),
                                        });
                                    }
                                });
                                
                                // Todos os botões
                                document.querySelectorAll('button, [role="button"]').forEach((el, i) => {
                                    const text = (el.textContent || '').trim();
                                    const classes = typeof el.className === 'string' ? el.className : '';
                                    if (text || classes.includes('download') || classes.includes('export') || classes.includes('save')) {
                                        result.buttons.push({
                                            index: i,
                                            text: text.substring(0, 40),
                                            classes: classes.substring(0, 60),
                                            tag: el.tagName,
                                        });
                                    }
                                });
                                
                                // Divs com classes relacionadas a vídeo/player
                                document.querySelectorAll('[class*="video"], [class*="player"], [class*="playback"], [class*="media"]').forEach((el, i) => {
                                    if (i < 10) {
                                        result.divs_with_video_class.push({
                                            index: i,
                                            tag: el.tagName,
                                            classes: typeof el.className === 'string' ? el.className.substring(0, 80) : '',
                                            id: el.id || '',
                                        });
                                    }
                                });
                                
                                // Sources de áudio/vídeo
                                document.querySelectorAll('source').forEach((el, i) => {
                                    result.sources.push({
                                        index: i,
                                        src: el.src || '',
                                        type: el.type || '',
                                    });
                                });
                                
                                // Imagens grandes (podem ser frames/thumbnails)
                                document.querySelectorAll('img').forEach((el, i) => {
                                    if (el.naturalWidth > 200 || el.width > 200) {
                                        result.images.push({
                                            index: i,
                                            src: (el.src || '').substring(0, 100),
                                            width: el.width || el.naturalWidth,
                                            height: el.height || el.naturalHeight,
                                        });
                                    }
                                });
                                
                                return result;
                            }
                        """)
                        
                        print("\n   📊 ANÁLISE COMPLETA DA PÁGINA DO RECORD:")
                        print(f"      🎬 Vídeos: {len(page_analysis.get('videos', []))}")
                        for v in page_analysis.get('videos', []):
                            print(f"         src: {v['src'][:80] if v['src'] else 'N/A'}")
                            for s in v.get('sources', []):
                                print(f"         source: {s[:80]}")
                        
                        print(f"      📺 Iframes: {len(page_analysis.get('iframes', []))}")
                        for i in page_analysis.get('iframes', []):
                            print(f"         src: {i['src'][:80] if i['src'] else 'N/A'}")
                        
                        print(f"      🎨 Canvas: {len(page_analysis.get('canvas', []))}")
                        for c in page_analysis.get('canvas', []):
                            print(f"         {c['width']}x{c['height']} | id: {c['id']} | classes: {c['classes'][:40]}")
                        
                        print(f"      🔗 Links de download: {len(page_analysis.get('links', []))}")
                        for l in page_analysis.get('links', []):
                            print(f"         {l['href'][:60]} | download: {l['hasDownload']}")
                        
                        print(f"      🎮 Divs video/player: {len(page_analysis.get('divs_with_video_class', []))}")
                        for d in page_analysis.get('divs_with_video_class', [])[:5]:
                            print(f"         {d['tag']} | {d['classes'][:50]}")
                        
                        print(f"      📦 Sources: {len(page_analysis.get('sources', []))}")
                        for s in page_analysis.get('sources', []):
                            print(f"         {s['src'][:80]} | type: {s['type']}")
                        
                        print(f"      🖼️ Imagens grandes: {len(page_analysis.get('images', []))}")
                        for img in page_analysis.get('images', [])[:3]:
                            print(f"         {img['width']}x{img['height']} | {img['src'][:60]}")
                        
                        print(f"      🔘 Botões: {len(page_analysis.get('buttons', []))}")
                        for b in page_analysis.get('buttons', [])[:10]:
                            print(f"         [{b['index']}] {b['tag']}: '{b['text']}' | {b['classes'][:30]}")
                        
                        # Capturar network requests para encontrar URLs de mídia
                        print("\n   🌐 Capturando requisições de rede...")
                        media_urls = []
                        
                        def capture_media(response):
                            url = response.url
                            content_type = response.headers.get('content-type', '')
                            if any(ext in url.lower() for ext in ['.mp4', '.webm', '.m3u8', '.ts', '.flv', 'video', 'media', 'flight_datas', 'airline']):
                                media_urls.append({'url': url, 'type': content_type})
                            if 'video' in content_type or 'octet-stream' in content_type:
                                media_urls.append({'url': url, 'type': content_type})
                        
                        new_page.on('response', capture_media)
                        
                        # Recarregar para capturar as requisições (timeout maior)
                        try:
                            new_page.reload()
                            new_page.wait_for_load_state("networkidle", timeout=60000)
                        except Exception as reload_error:
                            print(f"   ⚠️ Timeout no reload, continuando com dados capturados: {reload_error}")
                        
                        if media_urls:
                            print(f"   📡 URLs de mídia encontradas: {len(media_urls)}")
                            for m in media_urls[:10]:
                                print(f"      {m['url'][:80]} | {m['type']}")
                            
                            # Baixar os arquivos de mídia
                            print("\n   📥 Baixando arquivos de mídia...")
                            import requests
                            
                            # Pegar cookies da sessão
                            cookies = new_page.context.cookies()
                            cookie_dict = {c['name']: c['value'] for c in cookies}
                            
                            for idx, media in enumerate(media_urls):
                                url = media['url']
                                content_type = media['type']
                                
                                # Determinar extensão
                                if 'airline' in url:
                                    ext = '.bin'  # dados de rota
                                    filename = f"record_0_route_{idx}{ext}"
                                elif 'flight_records' in url:
                                    ext = '.bin'  # dados de voo
                                    filename = f"record_0_flight_data_{idx}{ext}"
                                else:
                                    ext = '.bin'
                                    filename = f"record_0_media_{idx}{ext}"
                                
                                filepath = os.path.join(records_path, filename)
                                
                                try:
                                    resp = requests.get(url, cookies=cookie_dict, timeout=60)
                                    if resp.status_code == 200:
                                        with open(filepath, 'wb') as f:
                                            f.write(resp.content)
                                        print(f"      ✅ Baixado: {filename} ({len(resp.content):,} bytes)")
                                    else:
                                        print(f"      ⚠️ Erro {resp.status_code}: {filename}")
                                except Exception as e:
                                    print(f"      ❌ Erro ao baixar {filename}: {e}")
                        else:
                            print("   ⚠️ Nenhuma URL de mídia capturada")
                        
                        # Salvar análise em arquivo JSON
                        import json
                        analysis_file = os.path.join(records_path, "record_0_analysis.json")
                        with open(analysis_file, 'w', encoding='utf-8') as f:
                            page_analysis['media_urls'] = media_urls
                            page_analysis['record_url'] = record_url
                            json.dump(page_analysis, f, indent=2, ensure_ascii=False)
                        print(f"\n   💾 Análise salva em: {analysis_file}")
                        
                        # Fechar a aba apenas se for uma nova aba
                        if is_new_tab:
                            new_page.close()
                            print("\n   🔄 Aba do record fechada")
                        else:
                            # Voltar para /records
                            page.goto("https://www.djiag.com/records")
                            page.wait_for_load_state("networkidle", timeout=30000)
                            print("\n   🔄 Voltou para /records")
                    else:
                        print("   ⚠️ Nenhum botão Playback encontrado")
                        
        except Exception as e:
            print(f"   ❌ Erro ao abrir record: {e}")
        
        print("\n   ✅ ETAPA 6 concluída!")
    
    elif "/login" not in final_url:
        # Logado mas não está em /records (ex: /mission)
        print("\n" + "=" * 60)
        print(" ⚠️ LOGIN OK, MAS NÃO ESTÁ EM /RECORDS")
        print(f"    URL: {final_url}")
        print("=" * 60)
        
        screenshot_path = os.path.join(os.path.dirname(__file__), "debug_screenshot.png")
        page.screenshot(path=screenshot_path)
        print(f"   📸 Screenshot salvo em: {screenshot_path}")
        
    else:
        print("\n" + "=" * 60)
        print(" ❌ LOGIN FALHOU")
        print(f"    URL: {final_url}")
        print("=" * 60)
        
        # Salvar screenshot para debug
        screenshot_path = os.path.join(os.path.dirname(__file__), "debug_screenshot.png")
        page.screenshot(path=screenshot_path)
        print(f"   📸 Screenshot salvo em: {screenshot_path}")
    
    # Manter browser aberto por alguns segundos
    print("\n🔄 Fechando browser em 5 segundos...")
    time.sleep(5)
    
    context.close()

print("\n✅ Script finalizado!")
