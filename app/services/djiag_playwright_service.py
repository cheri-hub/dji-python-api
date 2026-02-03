"""
Serviço de autenticação DJI AG usando Playwright.

Implementação que usa Playwright com Chrome do sistema para
fazer login automático e capturar tokens/cookies.

NOTA: Usa API síncrona do Playwright executada em thread separada
para compatibilidade com uvicorn no Windows (SelectorEventLoop).
"""

import asyncio
import base64
import concurrent.futures
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from app.config import settings
from app.models import (
    Record,
    RecordsListResponse,
    DownloadResponse,
    SessionStatus,
    LoginCredentials,
    AuthResponse,
)

# ThreadPoolExecutor global para execução do Playwright
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="playwright")


class DJIAgPlaywrightService:
    """
    Serviço DJI AG usando Playwright com Chrome do sistema.
    
    Executa Playwright em thread separada para evitar problemas
    com event loop no Windows.
    """
    
    def __init__(self):
        self._context: Optional[BrowserContext] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._is_authenticated: bool = False
        self._current_username: str = ""
        self._playwright = None
        self._storage_state_path = Path(settings.download_path) / "djiag_storage_state.json"
        self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_session_status(self) -> SessionStatus:
        """Retorna o status da sessão atual"""
        return SessionStatus(
            authenticated=self._is_authenticated,
            username=self._current_username if self._is_authenticated else None,
        )
    
    async def login(self, credentials: Optional[LoginCredentials] = None) -> AuthResponse:
        """
        Realiza login automático no DJI Account.
        
        O processo:
        1. Abre navegador Chrome
        2. Navega para djiag.com/login
        3. Preenche credenciais automaticamente
        4. Aguarda redirecionamento para página autenticada
        5. Salva storage state para uso posterior
        """
        username = credentials.username if credentials and credentials.username else settings.dji_username
        password = credentials.password if credentials and credentials.password else settings.dji_password
        
        if not username or not password:
            return AuthResponse(
                success=False,
                message="Credenciais não fornecidas. Configure DJI_USERNAME e DJI_PASSWORD no .env",
            )
        
        print(f"🔐 Iniciando autenticação DJI AG para: {username}")
        
        # Executa Playwright em thread separada
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self._login_sync,
            username,
            password,
        )
        
        return result
    
    def _login_sync(self, username: str, password: str) -> AuthResponse:
        """
        Execução síncrona do login (roda em thread separada).
        
        Fluxo homologado:
        1. Acessar https://www.djiag.com/br/records
        2. Se redirecionar para login: clicar checkbox "I have read..." + "Login with DJI account"
        3. Preencher credenciais no account.dji.com
        4. Verificar sucesso
        """
        try:
            from playwright.sync_api import sync_playwright
            from pathlib import Path
            
            # Diretório para dados persistentes do browser
            user_data_dir = str(Path(settings.download_path).parent / "browser_profile")
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)
            
            with sync_playwright() as p:
                print("   🚀 Iniciando browser com perfil persistente...")
                
                # Usar contexto persistente (mantém sessão entre execuções)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,  # Sempre visível para login
                    slow_mo=100,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    viewport={"width": 1280, "height": 800},
                )
                
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    
                    # Script anti-detecção
                    page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    """)
                    
                    # ============================================================
                    # ETAPA 1: Acessar djiag.com/br/records
                    # ============================================================
                    print("\n   📍 ETAPA 1: Acessando https://www.djiag.com/br/records ...")
                    page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
                    time.sleep(5)
                    
                    current_url = page.url
                    print(f"      URL após carregamento: {current_url}")
                    
                    # ============================================================
                    # ETAPA 2: Verificar se precisa login
                    # ============================================================
                    print("\n   📍 ETAPA 2: Verificando se precisa login...")
                    
                    needs_login = "/login" in current_url
                    
                    if not needs_login:
                        print("      ✅ Já está autenticado!")
                        self._is_authenticated = True
                        self._current_username = username
                        return AuthResponse(
                            success=True,
                            message="Sessão já autenticada",
                            session_status=self.get_session_status(),
                        )
                    
                    print("      ⚠️ Página de login detectada. Iniciando processo...")
                    
                    # Aceitar cookies se aparecer
                    try:
                        cookies_btn = page.locator("button:has-text('Accept'), button:has-text('Aceitar')").first
                        if cookies_btn.is_visible(timeout=2000):
                            cookies_btn.click()
                            print("      ✅ Cookies aceitos")
                            time.sleep(1)
                    except:
                        pass
                    
                    # Procurar e clicar no checkbox "I have read..."
                    try:
                        checkbox = page.locator("input[type='checkbox']").first
                        if checkbox.is_visible(timeout=5000):
                            checkbox.click()
                            print("      ✅ Checkbox 'I have read...' marcado")
                            time.sleep(1)
                    except:
                        print("      ℹ️ Checkbox não encontrado ou não visível")
                    
                    # Procurar e clicar no botão "Login with DJI account"
                    clicked = False
                    selectors = [
                        "button:has-text('Log in with DJI')",
                        "button:has-text('Login with DJI')",
                        "a:has-text('Log in with DJI')",
                        "a:has-text('Login with DJI')",
                        "[class*='login']",
                        "button:has-text('Log in')",
                        "button:has-text('Login')",
                    ]
                    
                    for selector in selectors:
                        try:
                            btn = page.locator(selector).first
                            if btn.is_visible(timeout=2000):
                                btn.click()
                                print(f"      ✅ Botão clicado: {selector}")
                                clicked = True
                                break
                        except:
                            continue
                    
                    if not clicked:
                        print("      ⚠️ Nenhum botão de login encontrado")
                    
                    time.sleep(3)
                    current_url = page.url
                    print(f"      URL após clique: {current_url}")
                    
                    # ============================================================
                    # ETAPA 3: Preencher credenciais no account.dji.com
                    # ============================================================
                    print("\n   📍 ETAPA 3: Preenchendo credenciais...")
                    
                    if "account.dji.com" in current_url:
                        print("      📍 Estamos no account.dji.com")
                        time.sleep(2)
                        
                        # Campo de email
                        try:
                            email_field = page.locator("input[name='username'], input[type='email'], input[type='text']").first
                            if email_field.is_visible(timeout=5000):
                                email_field.click()
                                time.sleep(0.3)
                                email_field.type(username, delay=30)
                                print("      ✅ Email preenchido")
                                time.sleep(0.5)
                        except Exception as e:
                            print(f"      ❌ Erro no email: {e}")
                        
                        # Campo de senha
                        try:
                            pass_field = page.locator("input[type='password']").first
                            if pass_field.is_visible(timeout=3000):
                                pass_field.click()
                                time.sleep(0.3)
                                pass_field.type(password, delay=30)
                                print("      ✅ Senha preenchida")
                                time.sleep(0.5)
                        except Exception as e:
                            print(f"      ❌ Erro na senha: {e}")
                        
                        # Clicar em Login - tentar vários seletores
                        print("      🖱️ Procurando botão de login...")
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
                                    print(f"      ✅ Botão Login clicado: {selector}")
                                    clicked = True
                                    break
                            except:
                                continue
                        
                        if not clicked:
                            # Tentar pressionar Enter no campo de senha
                            try:
                                pass_field = page.locator("input[type='password']").first
                                pass_field.press("Enter")
                                print("      ✅ Enter pressionado no campo de senha")
                                clicked = True
                            except:
                                print("      ❌ Não foi possível clicar no botão de login")
                        
                        # Aguardar redirecionamento
                        print("\n      ⏳ Aguardando redirecionamento...")
                        print("      💡 Se aparecer CAPTCHA, complete manualmente!")
                        
                        for i in range(60):
                            time.sleep(1)
                            current_url = page.url
                            if "account.dji.com/login" not in current_url and "account.dji.com/logout" not in current_url:
                                print(f"      ✅ Redirecionado para: {current_url}")
                                break
                            if i % 10 == 0 and i > 0:
                                print(f"      ⏳ Aguardando... ({i}s)")
                    else:
                        print(f"      ⚠️ Não estamos no account.dji.com. URL: {current_url}")
                    
                    # ============================================================
                    # ETAPA 4: Garantir redirecionamento para /records
                    # ============================================================
                    print("\n   📍 ETAPA 4: Garantindo redirecionamento para /records...")
                    
                    # Navegar explicitamente para /br/records
                    page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
                    time.sleep(3)
                    
                    current_url = page.url
                    print(f"      URL após navegação: {current_url}")
                    
                    # Se ainda não está em /records, tentar novamente
                    max_attempts = 3
                    for attempt in range(max_attempts):
                        if "/records" in current_url and "/login" not in current_url:
                            break
                        
                        print(f"      ⚠️ Não está em /records (tentativa {attempt + 1}/{max_attempts})")
                        
                        # Se está em /mission ou outra página, navegar para /records
                        if "/login" not in current_url:
                            print("      🔄 Redirecionando para /records...")
                            page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
                            time.sleep(3)
                            current_url = page.url
                            print(f"      URL: {current_url}")
                        else:
                            # Ainda em login, falhou
                            break
                    
                    final_url = page.url
                    print(f"      URL final: {final_url}")
                    
                    # Verificar se chegou na página autenticada (não em /login)
                    if "/login" not in final_url:
                        # Verificar se está em /records
                        if "/records" in final_url:
                            print("      ✅ Login bem-sucedido! Redirecionado para /records")
                        else:
                            print(f"      ✅ Login bem-sucedido! (URL: {final_url})")
                        
                        self._is_authenticated = True
                        self._current_username = username
                        return AuthResponse(
                            success=True,
                            message=f"Login realizado com sucesso. URL: {final_url}",
                            session_status=self.get_session_status(),
                        )
                    else:
                        page.screenshot(path=str(Path(settings.download_path) / "debug_login_final.png"))
                        return AuthResponse(
                            success=False,
                            message=f"Login incompleto. URL final: {final_url}",
                        )
                    
                finally:
                    context.close()
                    
        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()
            return AuthResponse(
                success=False,
                message=f"Erro no login: {str(e)}",
            )
    
    def _save_storage_state(self, context: BrowserContext) -> None:
        """Salva o storage state para reutilização."""
        try:
            context.storage_state(path=str(self._storage_state_path))
            print(f"   💾 Storage state salvo em: {self._storage_state_path}")
        except Exception as e:
            print(f"   ⚠️ Erro salvando storage state: {e}")
    
    async def get_records(self, page: int = 1, page_size: int = 10) -> RecordsListResponse:
        """Obtém a lista de records."""
        if not self._is_authenticated:
            return RecordsListResponse(
                success=False,
                message="Não autenticado. Faça login primeiro.",
                records=[],
            )
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self._get_records_sync,
            page,
            page_size,
        )
        
        return result
    
    def _get_records_sync(self, page_num: int, page_size: int) -> RecordsListResponse:
        """Obtém records usando o browser com contexto persistente."""
        try:
            from playwright.sync_api import sync_playwright
            from pathlib import Path
            
            # Usar o mesmo diretório de perfil do login
            user_data_dir = str(Path(settings.download_path).parent / "browser_profile")
            
            with sync_playwright() as p:
                # Usar contexto persistente (mantém sessão)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=settings.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    viewport={"width": 1280, "height": 800},
                )
                
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    
                    # Script anti-detecção
                    page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    """)
                    
                    # Navegar para records
                    print("   📍 Navegando para /br/records...")
                    page.goto("https://www.djiag.com/br/records", wait_until="networkidle", timeout=30000)
                    time.sleep(3)
                    
                    # Verificar se precisa fazer login
                    if "/login" in page.url:
                        print("   ❌ Sessão expirada, precisa fazer login novamente")
                        self._is_authenticated = False
                        context.close()
                        return RecordsListResponse(
                            success=False,
                            message="Sessão expirada. Faça login novamente.",
                            records=[],
                        )
                    
                    # Capturar dados da página
                    print("   🔍 Extraindo records...")
                    
                    # Aguardar tabela carregar
                    try:
                        page.wait_for_selector("table, .ant-table, [class*='record'], [class*='list']", timeout=10000)
                    except:
                        pass
                    
                    time.sleep(2)
                    
                    # Extrair dados via JavaScript
                    records_data = page.evaluate("""
                        () => {
                            let records = [];
                            
                            // Tentar tabela
                            const rows = document.querySelectorAll('table tbody tr, .ant-table-tbody tr');
                            rows.forEach((row, index) => {
                                const cells = row.querySelectorAll('td');
                                if (cells.length > 0) {
                                    records.push({
                                        id: row.getAttribute('data-row-key') || row.getAttribute('data-id') || `row_${index}`,
                                        name: cells[0] ? cells[0].textContent.trim() : '',
                                        date: cells[1] ? cells[1].textContent.trim() : '',
                                        status: cells[2] ? cells[2].textContent.trim() : '',
                                    });
                                }
                            });
                            
                            // Se não encontrou, tentar cards
                            if (records.length === 0) {
                                const cards = document.querySelectorAll('[class*="record-item"], [class*="flight-item"], [class*="task-item"]');
                                cards.forEach((card, index) => {
                                    records.push({
                                        id: card.getAttribute('data-id') || `card_${index}`,
                                        name: card.querySelector('[class*="name"], [class*="title"]')?.textContent?.trim() || card.textContent.substring(0, 50).trim(),
                                    });
                                });
                            }
                            
                            return {
                                records: records,
                                url: window.location.href,
                                html_sample: document.body.innerHTML.substring(0, 2000)
                            };
                        }
                    """)
                    
                    records = []
                    for item in records_data.get("records", []):
                        records.append(Record(
                            id=str(item.get("id", "")),
                            name=item.get("name", ""),
                            date=item.get("date"),
                            status=item.get("status"),
                        ))
                    
                    print(f"   ✅ Encontrados {len(records)} records")
                    
                    if not records:
                        # Retornar amostra do HTML para debug
                        context.close()
                        return RecordsListResponse(
                            success=True,
                            message=f"Nenhum record encontrado. URL: {records_data.get('url')}",
                            records=[],
                            total=0,
                        )
                    
                    context.close()
                    return RecordsListResponse(
                        success=True,
                        message=f"Encontrados {len(records)} records",
                        records=records,
                        total=len(records),
                        page=page_num,
                        page_size=page_size,
                    )
                    
                finally:
                    pass  # Contexto já fechado nos returns acima
                    
        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()
            return RecordsListResponse(
                success=False,
                message=f"Erro: {str(e)}",
                records=[],
            )
    
    async def download_record(self, record_id: str) -> DownloadResponse:
        """Faz download de um record específico."""
        if not self._is_authenticated:
            return DownloadResponse(
                success=False,
                message="Não autenticado. Faça login primeiro.",
            )
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self._download_record_sync,
            record_id,
        )
        
        return result
    
    def _download_record_sync(self, record_id: str) -> DownloadResponse:
        """Download de record usando o browser com contexto persistente."""
        try:
            from playwright.sync_api import sync_playwright
            from pathlib import Path
            
            # Usar o mesmo diretório de perfil do login
            user_data_dir = str(Path(settings.download_path).parent / "browser_profile")
            
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=settings.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    viewport={"width": 1280, "height": 800},
                )
                
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    
                    page.goto("https://www.djiag.com/br/records", wait_until="networkidle", timeout=30000)
                    time.sleep(2)
                    
                    # Procurar e clicar no botão de download
                    download_clicked = page.evaluate(f"""
                        () => {{
                            const rows = document.querySelectorAll('table tbody tr, .ant-table-tbody tr');
                            for (const row of rows) {{
                                const rowId = row.getAttribute('data-row-key') || row.getAttribute('data-id');
                                if (rowId === '{record_id}' || row.textContent.includes('{record_id}')) {{
                                    const downloadBtn = row.querySelector('[class*="download"], a[download], button[title*="download"]');
                                    if (downloadBtn) {{
                                        downloadBtn.click();
                                        return true;
                                    }}
                                }}
                            }}
                            return false;
                        }}
                    """)
                    
                    if download_clicked:
                        time.sleep(3)
                        context.close()
                        return DownloadResponse(
                            success=True,
                            message=f"Download do record {record_id} iniciado",
                        )
                    else:
                        context.close()
                        return DownloadResponse(
                            success=False,
                            message=f"Record {record_id} não encontrado",
                        )
                        
                finally:
                    pass  # Contexto já fechado
                    
        except Exception as e:
            return DownloadResponse(
                success=False,
                message=f"Erro: {str(e)}",
            )
    
    async def download_all(self) -> DownloadResponse:
        """Usa o botão de download all do site."""
        if not self._is_authenticated:
            return DownloadResponse(
                success=False,
                message="Não autenticado. Faça login primeiro.",
            )
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            self._download_all_sync,
        )
        
        return result
    
    def _download_all_sync(self) -> DownloadResponse:
        """Download all usando o browser com contexto persistente."""
        try:
            from playwright.sync_api import sync_playwright
            from pathlib import Path
            
            # Usar o mesmo diretório de perfil do login
            user_data_dir = str(Path(settings.download_path).parent / "browser_profile")
            
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=settings.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    viewport={"width": 1280, "height": 800},
                )
                
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    
                    page.goto("https://www.djiag.com/br/records", wait_until="networkidle", timeout=30000)
                    time.sleep(2)
                    
                    # Procurar botão de download all
                    download_clicked = page.evaluate("""
                        () => {
                            const buttons = document.querySelectorAll('button, a');
                            for (const btn of buttons) {
                                const text = btn.textContent.toLowerCase();
                                if (text.includes('download') && text.includes('all')) {
                                    btn.click();
                                    return true;
                                }
                            }
                            
                            // Tentar seletores específicos
                            const selectors = ['.download-all', '[class*="download-all"]', 'button[title*="all"]'];
                            for (const sel of selectors) {
                                const el = document.querySelector(sel);
                                if (el) {
                                    el.click();
                                    return true;
                                }
                            }
                            
                            return false;
                        }
                    """)
                    
                    if download_clicked:
                        time.sleep(3)
                        context.close()
                        return DownloadResponse(
                            success=True,
                            message="Download All iniciado",
                        )
                    else:
                        context.close()
                        return DownloadResponse(
                            success=False,
                            message="Botão de Download All não encontrado",
                        )
                        
                finally:
                    pass  # Contexto já fechado
                    
        except Exception as e:
            return DownloadResponse(
                success=False,
                message=f"Erro: {str(e)}",
            )
    
    def close(self) -> None:
        """Limpa recursos."""
        self._is_authenticated = False
        self._current_username = ""
        print("🔒 Sessão encerrada")


# Singleton
_playwright_service: Optional[DJIAgPlaywrightService] = None


def get_playwright_service() -> DJIAgPlaywrightService:
    """Retorna a instância singleton do serviço"""
    global _playwright_service
    if _playwright_service is None:
        _playwright_service = DJIAgPlaywrightService()
    return _playwright_service
