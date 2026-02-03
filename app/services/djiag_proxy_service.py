"""
Serviço de proxy para DJI AG.

Este serviço usa o Selenium para manter uma sessão de browser aberta e 
executar requisições JavaScript diretamente no contexto do browser autenticado.
Isso permite contornar a necessidade de gerar a assinatura WebAssembly.
"""
import asyncio
import json
import time
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


class DJIAgProxyService:
    """
    Serviço que usa o browser como proxy para fazer requisições à API do DJI AG.
    
    O JavaScript do site já sabe como gerar as assinaturas via WebAssembly,
    então usamos o browser para fazer as requisições e capturamos os resultados.
    """
    
    def __init__(self):
        self._driver: Optional[webdriver.Chrome] = None
        self._is_authenticated: bool = False
        self._current_username: str = ""
    
    def _get_driver(self) -> webdriver.Chrome:
        """Retorna ou cria o driver do Selenium"""
        if self._driver is None:
            options = Options()
            # Não usar headless para debug, mas pode ser habilitado depois
            if settings.headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            
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
        print("🔒 Browser fechado")
    
    def get_session_status(self) -> SessionStatus:
        """Retorna o status da sessão atual"""
        return SessionStatus(
            authenticated=self._is_authenticated,
            username=self._current_username if self._is_authenticated else None,
        )
    
    async def wait_for_manual_login(self) -> AuthResponse:
        """
        Abre o browser e aguarda o usuário fazer login manualmente.
        Retorna quando detecta que o usuário está autenticado.
        """
        try:
            driver = self._get_driver()
            
            print("🔐 Abrindo página de login...")
            driver.get("https://www.djiag.com/login")
            
            # Aguardar até 5 minutos para o usuário fazer login
            print("⏳ Aguardando login manual (timeout: 5 minutos)...")
            start_time = time.time()
            timeout = 300  # 5 minutos
            
            while time.time() - start_time < timeout:
                await asyncio.sleep(2)
                current_url = driver.current_url
                
                # Verificar se chegou na página de records ou outra página autenticada
                if any(x in current_url for x in ["/records", "/dashboard", "/task"]):
                    self._is_authenticated = True
                    print("✅ Login detectado!")
                    return AuthResponse(
                        success=True,
                        message="Login realizado com sucesso",
                        session_status=self.get_session_status(),
                    )
            
            return AuthResponse(
                success=False,
                message="Timeout aguardando login manual",
            )
            
        except Exception as e:
            return AuthResponse(
                success=False,
                message=f"Erro: {str(e)}",
            )
    
    async def login_with_credentials(self, credentials: Optional[LoginCredentials] = None) -> AuthResponse:
        """
        Tenta fazer login automaticamente.
        Se falhar, aguarda login manual.
        """
        try:
            username = credentials.username if credentials and credentials.username else settings.dji_username
            password = credentials.password if credentials and credentials.password else settings.dji_password
            
            if not username or not password:
                return AuthResponse(
                    success=False,
                    message="Credenciais não fornecidas. Configure DJI_USERNAME e DJI_PASSWORD no .env",
                )
            
            driver = self._get_driver()
            
            print("🔐 Iniciando processo de login...")
            
            # Acessar página de login
            driver.get("https://www.djiag.com/login")
            await asyncio.sleep(3)
            
            # Verificar se já está logado
            if any(x in driver.current_url for x in ["/records", "/dashboard"]):
                self._is_authenticated = True
                self._current_username = username
                return AuthResponse(
                    success=True,
                    message="Já estava logado",
                    session_status=self.get_session_status(),
                )
            
            # Aguardar até 2 minutos para login manual
            print("⏳ Aguardando login (faça login manualmente no browser)...")
            start_time = time.time()
            timeout = 120  # 2 minutos
            
            while time.time() - start_time < timeout:
                await asyncio.sleep(2)
                
                if any(x in driver.current_url for x in ["/records", "/dashboard", "/task"]):
                    self._is_authenticated = True
                    self._current_username = username
                    print("✅ Login detectado!")
                    return AuthResponse(
                        success=True,
                        message="Login realizado com sucesso",
                        session_status=self.get_session_status(),
                    )
            
            return AuthResponse(
                success=False,
                message="Timeout - faça login manualmente e tente novamente",
            )
            
        except Exception as e:
            return AuthResponse(
                success=False,
                message=f"Erro: {str(e)}",
            )
    
    async def get_records(self, page: int = 1, page_size: int = 10) -> RecordsListResponse:
        """
        Obtém a lista de records navegando para a página e extraindo os dados do DOM.
        """
        if not self._is_authenticated:
            return RecordsListResponse(
                success=False,
                message="Não autenticado. Faça login primeiro.",
                records=[],
            )
        
        try:
            driver = self._get_driver()
            
            # Navegar para a página de records
            if "records" not in driver.current_url:
                driver.get("https://www.djiag.com/records")
                await asyncio.sleep(3)
            
            # Aguardar carregamento da tabela
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table, .ant-table, .el-table, [class*='record']"))
            )
            await asyncio.sleep(2)
            
            # Extrair dados usando JavaScript
            records_data = driver.execute_script("""
                // Tentar encontrar dados de records no estado do Vue/React ou no DOM
                let records = [];
                
                // Opção 1: Procurar na store do Vue
                if (window.__NUXT__ && window.__NUXT__.state) {
                    const state = window.__NUXT__.state;
                    if (state.records) records = state.records;
                }
                
                // Opção 2: Procurar elementos da tabela
                if (records.length === 0) {
                    const rows = document.querySelectorAll('table tbody tr, .ant-table-tbody tr, .el-table__body tr');
                    rows.forEach((row, index) => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length > 0) {
                            records.push({
                                id: row.getAttribute('data-row-key') || row.getAttribute('data-id') || `row_${index}`,
                                name: cells[0] ? cells[0].textContent.trim() : '',
                                date: cells[1] ? cells[1].textContent.trim() : '',
                                status: cells[2] ? cells[2].textContent.trim() : '',
                                raw_html: row.innerHTML
                            });
                        }
                    });
                }
                
                // Opção 3: Procurar cards de record
                if (records.length === 0) {
                    const cards = document.querySelectorAll('[class*="record"], [class*="flight"], [class*="task"]');
                    cards.forEach((card, index) => {
                        records.push({
                            id: card.getAttribute('data-id') || `card_${index}`,
                            name: card.textContent.substring(0, 100).trim(),
                            raw_html: card.outerHTML.substring(0, 500)
                        });
                    });
                }
                
                return {
                    records: records,
                    page_html: document.body.innerHTML.substring(0, 10000)
                };
            """)
            
            records = []
            for item in records_data.get("records", []):
                records.append(Record(
                    id=str(item.get("id", "")),
                    name=item.get("name", ""),
                    date=item.get("date"),
                    status=item.get("status"),
                ))
            
            # Se não encontrou records, retornar HTML para debug
            if not records:
                return RecordsListResponse(
                    success=True,
                    message=f"Nenhum record encontrado. Debug HTML: {records_data.get('page_html', '')[:500]}...",
                    records=[],
                    total=0,
                )
            
            return RecordsListResponse(
                success=True,
                message=f"Encontrados {len(records)} records",
                records=records,
                total=len(records),
                page=page,
                page_size=page_size,
            )
            
        except Exception as e:
            return RecordsListResponse(
                success=False,
                message=f"Erro ao obter records: {str(e)}",
                records=[],
            )
    
    async def get_records_via_intercept(self) -> RecordsListResponse:
        """
        Obtém records interceptando a requisição da API.
        Usa JavaScript para fazer a requisição e capturar a resposta.
        """
        if not self._is_authenticated:
            return RecordsListResponse(
                success=False,
                message="Não autenticado. Faça login primeiro.",
                records=[],
            )
        
        try:
            driver = self._get_driver()
            
            # Garantir que está na página do DJI AG
            if "djiag.com" not in driver.current_url:
                driver.get("https://www.djiag.com/records")
                await asyncio.sleep(3)
            
            # Executar a requisição usando o fetch do browser (que já tem todas as configs)
            result = driver.execute_script("""
                return new Promise(async (resolve) => {
                    try {
                        // Recarregar a página de records para capturar a requisição
                        const originalFetch = window.fetch;
                        let apiResponse = null;
                        
                        window.fetch = async (...args) => {
                            const response = await originalFetch(...args);
                            const url = typeof args[0] === 'string' ? args[0] : args[0].url;
                            
                            if (url.includes('flight_records') || url.includes('records')) {
                                const clonedResponse = response.clone();
                                apiResponse = await clonedResponse.json();
                            }
                            
                            return response;
                        };
                        
                        // Disparar um refresh da página ou um evento que force o reload dos dados
                        // Tentar encontrar o método de refresh
                        if (window.__NUXT__ && window.__NUXT__.$root && window.__NUXT__.$root.$store) {
                            const store = window.__NUXT__.$root.$store;
                            if (store.dispatch) {
                                await store.dispatch('fetchRecords');
                            }
                        }
                        
                        // Aguardar um pouco
                        await new Promise(r => setTimeout(r, 2000));
                        
                        window.fetch = originalFetch;
                        
                        if (apiResponse) {
                            resolve({ success: true, data: apiResponse });
                        } else {
                            resolve({ success: false, message: 'Não foi possível capturar a resposta' });
                        }
                    } catch (e) {
                        resolve({ success: false, message: e.toString() });
                    }
                });
            """)
            
            if result.get("success") and result.get("data"):
                data = result.get("data", {})
                records = []
                
                # Parsear conforme estrutura da API
                items = data.get("data", {}).get("records", [])
                for item in items:
                    records.append(Record(
                        id=str(item.get("id", "")),
                        name=item.get("name", ""),
                        date=item.get("created_at"),
                        status=item.get("status"),
                    ))
                
                return RecordsListResponse(
                    success=True,
                    message="Records obtidos via interceptação",
                    records=records,
                    total=len(records),
                )
            else:
                return RecordsListResponse(
                    success=False,
                    message=result.get("message", "Erro desconhecido"),
                    records=[],
                )
            
        except Exception as e:
            return RecordsListResponse(
                success=False,
                message=f"Erro: {str(e)}",
                records=[],
            )
    
    async def download_record(self, record_id: str) -> DownloadResponse:
        """
        Faz download de um record específico clicando no botão de download.
        """
        if not self._is_authenticated:
            return DownloadResponse(
                success=False,
                message="Não autenticado. Faça login primeiro.",
            )
        
        try:
            driver = self._get_driver()
            
            # Navegar para a página de records
            if "records" not in driver.current_url:
                driver.get("https://www.djiag.com/records")
                await asyncio.sleep(3)
            
            # Tentar encontrar e clicar no botão de download do record
            download_clicked = driver.execute_script(f"""
                // Procurar o record pelo ID
                const rows = document.querySelectorAll('table tbody tr, .ant-table-tbody tr');
                for (const row of rows) {{
                    const rowId = row.getAttribute('data-row-key') || row.getAttribute('data-id');
                    if (rowId === '{record_id}' || row.textContent.includes('{record_id}')) {{
                        // Encontrar botão de download
                        const downloadBtn = row.querySelector('[class*="download"], a[download], button[title*="download"]');
                        if (downloadBtn) {{
                            downloadBtn.click();
                            return true;
                        }}
                    }}
                }}
                return false;
            """)
            
            if download_clicked:
                await asyncio.sleep(2)
                return DownloadResponse(
                    success=True,
                    message=f"Download do record {record_id} iniciado",
                )
            else:
                return DownloadResponse(
                    success=False,
                    message=f"Record {record_id} não encontrado ou sem botão de download",
                )
            
        except Exception as e:
            return DownloadResponse(
                success=False,
                message=f"Erro: {str(e)}",
            )
    
    async def download_all(self) -> DownloadResponse:
        """
        Usa o botão de download all do site.
        """
        if not self._is_authenticated:
            return DownloadResponse(
                success=False,
                message="Não autenticado. Faça login primeiro.",
            )
        
        try:
            driver = self._get_driver()
            
            # Navegar para a página de records
            if "records" not in driver.current_url:
                driver.get("https://www.djiag.com/records")
                await asyncio.sleep(3)
            
            # Procurar e clicar no botão de download all
            download_clicked = driver.execute_script("""
                // Procurar botão de download all
                const selectors = [
                    'button:contains("Download All")',
                    '[class*="download-all"]',
                    'button[title*="all"]',
                    '.download-all-btn'
                ];
                
                for (const selector of selectors) {
                    try {
                        const btn = document.querySelector(selector);
                        if (btn) {
                            btn.click();
                            return true;
                        }
                    } catch (e) {}
                }
                
                // Fallback: procurar por texto
                const buttons = document.querySelectorAll('button, a');
                for (const btn of buttons) {
                    if (btn.textContent.toLowerCase().includes('download') && 
                        btn.textContent.toLowerCase().includes('all')) {
                        btn.click();
                        return true;
                    }
                }
                
                return false;
            """)
            
            if download_clicked:
                await asyncio.sleep(2)
                return DownloadResponse(
                    success=True,
                    message="Download All iniciado",
                )
            else:
                return DownloadResponse(
                    success=False,
                    message="Botão de Download All não encontrado",
                )
            
        except Exception as e:
            return DownloadResponse(
                success=False,
                message=f"Erro: {str(e)}",
            )


# Singleton
_proxy_service: Optional[DJIAgProxyService] = None


def get_proxy_service() -> DJIAgProxyService:
    """Retorna a instância singleton do serviço"""
    global _proxy_service
    if _proxy_service is None:
        _proxy_service = DJIAgProxyService()
    return _proxy_service
