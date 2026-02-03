"""
Serviço de login usando Selenium para capturar o token e fazer requisições autenticadas.
O Selenium é usado apenas para o login inicial, depois as requisições são feitas via HTTP.
"""
import asyncio
import json
import time
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from app.config import settings
from app.models import (
    Record,
    RecordsListResponse,
    DownloadResponse,
    SessionStatus,
    LoginCredentials,
    AuthResponse,
)


class DJIAgSeleniumService:
    """Serviço para DJI AG usando Selenium para login e HTTP para requisições"""
    
    def __init__(self):
        self._driver: Optional[webdriver.Chrome] = None
        self._is_authenticated: bool = False
        self._current_username: str = ""
        self._captured_requests: List[Dict] = []
    
    def _get_driver(self) -> webdriver.Chrome:
        """Retorna ou cria o driver do Selenium"""
        if self._driver is None:
            options = Options()
            if settings.headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            
            # Habilitar logging de rede para capturar requisições
            options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
            
            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
        
        return self._driver
    
    def close(self) -> None:
        """Fecha o browser"""
        if self._driver:
            self._driver.quit()
            self._driver = None
        self._is_authenticated = False
        self._current_username = ""
        print("🔒 Browser closed")
    
    def _capture_network_requests(self) -> List[Dict]:
        """Captura requisições de rede do browser"""
        requests = []
        try:
            logs = self._driver.get_log("performance")
            for log in logs:
                try:
                    message = json.loads(log["message"])["message"]
                    if message["method"] == "Network.requestWillBeSent":
                        request = message["params"]["request"]
                        if "kr-ag2-api.dji.com" in request.get("url", ""):
                            requests.append({
                                "url": request.get("url"),
                                "method": request.get("method"),
                                "headers": request.get("headers", {}),
                            })
                except:
                    continue
        except:
            pass
        return requests
    
    async def login(self, credentials: Optional[LoginCredentials] = None) -> AuthResponse:
        """Realiza login no DJI Account via Selenium"""
        try:
            username = credentials.username if credentials and credentials.username else settings.dji_username
            password = credentials.password if credentials and credentials.password else settings.dji_password
            
            if not username or not password:
                return AuthResponse(
                    success=False,
                    message="Credentials not provided. Set DJI_USERNAME and DJI_PASSWORD in .env or pass them in the request.",
                )
            
            driver = self._get_driver()
            
            print("🔐 Starting Selenium login process...")
            
            # Acessar página de login
            print("   Step 1: Navigating to djiag.com/login...")
            driver.get("https://www.djiag.com/login")
            await asyncio.sleep(3)
            
            # Verificar se já está na página de records
            if "records" in driver.current_url:
                print("   Already logged in!")
                self._is_authenticated = True
                self._current_username = username
                return AuthResponse(
                    success=True,
                    message="Already logged in",
                    session_status=self.get_session_status(),
                )
            
            # Esperar redirecionamento para DJI Account
            print("   Step 2: Waiting for DJI Account login page...")
            await asyncio.sleep(2)
            
            # Verificar se está na página do SmartFarm
            if "smartfarm" in driver.current_url.lower():
                print("   Found SmartFarm intermediate page...")
                try:
                    # Clicar no checkbox e botão de continuar
                    checkbox = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='checkbox'], .ant-checkbox-input, .el-checkbox__input"))
                    )
                    checkbox.click()
                    await asyncio.sleep(0.5)
                    
                    submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .submit-btn, .ant-btn-primary")
                    submit_btn.click()
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"   SmartFarm page handling: {e}")
            
            # Preencher credenciais
            print("   Step 3: Filling login credentials...")
            try:
                # Esperar campo de email
                email_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[placeholder*='mail']"))
                )
                email_field.clear()
                email_field.send_keys(username)
                
                # Campo de senha
                password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                password_field.clear()
                password_field.send_keys(password)
                
                # Botão de login
                await asyncio.sleep(1)
                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .login-btn, .submit-btn")
                login_btn.click()
                
                print("   Step 4: Waiting for login to complete...")
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"   Login form error: {e}")
                # Salvar screenshot para debug
                driver.save_screenshot(str(settings.get_download_path() / "debug_login.png"))
            
            # Verificar se login foi bem sucedido
            await asyncio.sleep(3)
            
            if "records" in driver.current_url or "djiag.com" in driver.current_url and "login" not in driver.current_url:
                self._is_authenticated = True
                self._current_username = username
                
                # Navegar para records para capturar requisições autenticadas
                print("   Step 5: Navigating to records to capture authenticated requests...")
                driver.get("https://www.djiag.com/records")
                await asyncio.sleep(5)
                
                # Capturar requisições
                self._captured_requests = self._capture_network_requests()
                print(f"   Captured {len(self._captured_requests)} API requests")
                
                # Salvar para debug
                if self._captured_requests:
                    debug_path = settings.get_download_path() / "captured_requests.json"
                    with open(debug_path, "w") as f:
                        json.dump(self._captured_requests, f, indent=2)
                    print(f"   Saved captured requests to: {debug_path}")
                
                print("✅ Login successful!")
                return AuthResponse(
                    success=True,
                    message="Login successful",
                    session_status=self.get_session_status(),
                )
            
            # Login falhou
            driver.save_screenshot(str(settings.get_download_path() / "debug_login_failed.png"))
            return AuthResponse(
                success=False,
                message=f"Login failed. Current URL: {driver.current_url}",
            )
            
        except Exception as e:
            import traceback
            print(f"❌ Login error: {e}")
            print(traceback.format_exc())
            return AuthResponse(
                success=False,
                message=f"Login error: {str(e)}",
            )
    
    async def get_records(self) -> RecordsListResponse:
        """Obtém a lista de records usando o browser"""
        try:
            if not self._is_authenticated:
                return RecordsListResponse(
                    success=False,
                    message="Not authenticated. Please login first.",
                )
            
            driver = self._get_driver()
            
            print("📋 Fetching records list via browser...")
            
            # Navegar para a página de records
            if "records" not in driver.current_url:
                driver.get("https://www.djiag.com/records")
                await asyncio.sleep(5)
            
            # Capturar requisições para a API
            requests = self._capture_network_requests()
            
            # Procurar pela resposta de flight_records no log de rede
            records = []
            
            # Executar JavaScript para pegar dados da página
            try:
                # Tentar extrair dados do estado da aplicação
                data = driver.execute_script("""
                    // Tentar várias formas de acessar os dados
                    if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                    if (window.__NUXT__) return window.__NUXT__;
                    
                    // Procurar em elementos da tabela
                    const rows = document.querySelectorAll('tr[data-row-key], .ant-table-row, .record-row');
                    const records = [];
                    rows.forEach(row => {
                        const id = row.getAttribute('data-row-key') || row.getAttribute('data-id');
                        if (id) {
                            records.push({
                                id: id,
                                text: row.innerText
                            });
                        }
                    });
                    return {records: records};
                """)
                
                if data and isinstance(data, dict):
                    records_data = data.get("records", [])
                    for r in records_data:
                        if isinstance(r, dict) and r.get("id"):
                            records.append(Record(
                                id=str(r.get("id")),
                                name=r.get("text", f"Record {r.get('id')}"),
                                url=f"https://www.djiag.com/record/{r.get('id')}",
                            ))
                    
            except Exception as e:
                print(f"   JavaScript extraction error: {e}")
            
            # Se não conseguiu extrair via JS, usar as requisições capturadas
            if not records and self._captured_requests:
                for req in self._captured_requests:
                    if "flight_records" in req.get("url", ""):
                        # Os headers desta requisição podem ser usados para fazer chamadas HTTP
                        headers = req.get("headers", {})
                        auth_token = headers.get("x-auth-token")
                        signature = headers.get("signature")
                        if auth_token:
                            print(f"   Found auth token in captured request")
                            print(f"   Token: {auth_token[:50]}...")
                            if signature:
                                print(f"   Signature: {signature}")
            
            # Fallback: parsear HTML
            if not records:
                html = driver.page_source
                record_pattern = r'/record/(\d+)'
                record_ids = list(set(re.findall(record_pattern, html)))
                
                for record_id in record_ids:
                    records.append(Record(
                        id=record_id,
                        name=f"Record {record_id}",
                        url=f"https://www.djiag.com/record/{record_id}",
                    ))
            
            print(f"✅ Found {len(records)} records")
            
            return RecordsListResponse(
                success=True,
                records=records,
                total=len(records),
            )
            
        except Exception as e:
            import traceback
            print(f"❌ Error fetching records: {e}")
            print(traceback.format_exc())
            return RecordsListResponse(
                success=False,
                message=f"Error fetching records: {str(e)}",
            )
    
    async def download_record(self, record_id: str) -> DownloadResponse:
        """Faz download de um record via browser"""
        try:
            if not self._is_authenticated:
                return DownloadResponse(
                    success=False,
                    message="Not authenticated. Please login first.",
                )
            
            driver = self._get_driver()
            
            print(f"📥 Downloading record: {record_id}")
            
            # Navegar para a página do record
            driver.get(f"https://www.djiag.com/record/{record_id}")
            await asyncio.sleep(3)
            
            # Procurar botão de download
            try:
                download_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.download, .download-btn, [data-action='download']"))
                )
                download_btn.click()
                await asyncio.sleep(5)
                
                return DownloadResponse(
                    success=True,
                    message="Download initiated. Check your downloads folder.",
                    file_path=str(settings.get_download_path()),
                )
            except Exception as e:
                return DownloadResponse(
                    success=False,
                    message=f"Could not find download button: {e}",
                )
            
        except Exception as e:
            return DownloadResponse(
                success=False,
                message=f"Download error: {str(e)}",
            )
    
    async def download_all(self) -> DownloadResponse:
        """Faz download de todos os records via browser"""
        try:
            if not self._is_authenticated:
                return DownloadResponse(
                    success=False,
                    message="Not authenticated. Please login first.",
                )
            
            driver = self._get_driver()
            
            print("📥 Downloading all records...")
            
            # Navegar para a página de records
            driver.get("https://www.djiag.com/records")
            await asyncio.sleep(3)
            
            # Procurar botão de download all
            try:
                download_all_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.download-all, .download-all-btn, [data-action='download-all']"))
                )
                download_all_btn.click()
                await asyncio.sleep(10)
                
                return DownloadResponse(
                    success=True,
                    message="Download All initiated. Check your downloads folder.",
                    file_path=str(settings.get_download_path()),
                )
            except Exception as e:
                return DownloadResponse(
                    success=False,
                    message=f"Could not find Download All button: {e}",
                )
            
        except Exception as e:
            return DownloadResponse(
                success=False,
                message=f"Download All error: {str(e)}",
            )
    
    def get_session_status(self) -> SessionStatus:
        """Retorna o status da sessão atual"""
        return SessionStatus(
            is_authenticated=self._is_authenticated,
            username=self._current_username if self._is_authenticated else None,
        )
    
    def is_logged_in(self) -> bool:
        """Verifica se está autenticado"""
        return self._is_authenticated


# Singleton instance
dji_selenium_service = DJIAgSeleniumService()
