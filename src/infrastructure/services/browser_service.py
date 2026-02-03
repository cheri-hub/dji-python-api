"""
Playwright Browser Service - Usando sync API em thread dedicada

NOTA: Usa API sincrona do Playwright executada em uma unica thread dedicada
para garantir compatibilidade e evitar problemas de threading.
Todas as operacoes do Playwright DEVEM rodar na mesma thread
onde o browser foi inicializado. Esta classe garante isso.
"""
import asyncio
import threading
import queue
import time
from functools import partial
from typing import Optional, Any, Callable
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from ...domain.interfaces import IBrowserService
from ..config import get_settings


class PlaywrightThread:
    """
    Thread dedicada para todas as operacoes do Playwright.
    Playwright requer que todas as operacoes sejam feitas na mesma thread
    onde o browser foi inicializado. Esta classe garante isso.
    """
    
    def __init__(self):
        self._task_queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._settings = get_settings()
        self._lock = threading.Lock()
    
    def _worker(self):
        """Worker que processa tarefas na thread dedicada"""
        while self._running:
            try:
                task = self._task_queue.get(timeout=1)
                if task is None:
                    break
                    
                func, args, kwargs, result_queue = task
                try:
                    result = func(*args, **kwargs)
                    result_queue.put(('success', result))
                except Exception as e:
                    result_queue.put(('error', e))
            except queue.Empty:
                continue
    
    def start(self):
        """Inicia a thread do worker"""
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._worker, daemon=True)
                self._thread.start()
    
    def stop(self):
        """Para a thread do worker"""
        with self._lock:
            self._running = False
            if self._thread:
                self._task_queue.put(None)
                self._thread.join(timeout=5)
                self._thread = None
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Executa uma funcao na thread dedicada e retorna o resultado"""
        if not self._running:
            self.start()
        
        result_queue = queue.Queue()
        self._task_queue.put((func, args, kwargs, result_queue))
        
        status, result = result_queue.get()
        if status == 'error':
            raise result
        return result
    
    def _do_initialize(self):
        """Inicializa o Playwright na thread dedicada"""
        # Verifica se precisa reinicializar
        needs_init = False
        
        if self._playwright is None:
            needs_init = True
        elif self._context is None:
            needs_init = True
        else:
            # Verifica se o browser ainda esta ativo
            try:
                browser = self._context.browser
                if browser is None or not browser.is_connected():
                    needs_init = True
            except Exception:
                needs_init = True
        
        if not needs_init:
            return
        
        # Limpa recursos antigos se existirem
        self._cleanup_resources()
        
        # Inicializa o Playwright
        self._playwright = sync_playwright().start()
        
        # Args para Docker/Linux (obrigatorios em container)
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',                    # Obrigatorio em Docker
            '--disable-dev-shm-usage',         # Evita crash por memoria compartilhada
            '--disable-gpu',                   # Sem GPU no container
            '--disable-setuid-sandbox',        # Seguranca container
            '--disable-software-rasterizer',   # Performance
        ]
        
        # Lanca o browser com contexto persistente (mesma config do test_hybrid_login.py)
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self._settings.browser_profile_dir,
            headless=self._settings.browser_headless,
            slow_mo=100,
            args=browser_args,
            ignore_default_args=['--enable-automation'],
            viewport={'width': 1280, 'height': 800}
        )
        
        # Usa a primeira pagina ou cria uma nova
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()
        
        # Script anti-deteccao (mesma config do test_hybrid_login.py)
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
    
    def _cleanup_resources(self):
        """Limpa recursos do Playwright"""
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        
        self._context = None
        self._page = None
        self._playwright = None
    
    def _do_close(self):
        """Fecha o browser na thread dedicada"""
        self._cleanup_resources()
    
    def _do_is_logged_in(self) -> bool:
        """Verifica login na thread dedicada"""
        self._do_initialize()
        
        try:
            # Verificar URL atual primeiro
            current_url = self._page.url
            
            # Se ja esta em /records e nao em /login, esta logado
            if "/records" in current_url and "/login" not in current_url:
                return True
            
            # Se nao, navegar para records e verificar
            self._page.goto("https://www.djiag.com/br/records", wait_until="networkidle", timeout=60000)
            time.sleep(3)
            
            current_url = self._page.url
            
            # Se esta em /records e nao em /login, esta logado
            if "/records" in current_url and "/login" not in current_url:
                return True
            
            return False
            
        except Exception:
            return False
    
    def _do_navigate(self, url: str) -> str:
        """Navega para uma URL na thread dedicada"""
        self._do_initialize()
        self._page.goto(url, wait_until="networkidle", timeout=60000)
        return self._page.content()
    
    def _do_get_page_content(self) -> str:
        """Obtem conteudo da pagina na thread dedicada"""
        self._do_initialize()
        return self._page.content()
    
    def _do_execute_script(self, script: str) -> Any:
        """Executa JavaScript na thread dedicada"""
        self._do_initialize()
        return self._page.evaluate(script)
    
    def _do_wait_for_selector(self, selector: str, timeout: int = 30000) -> bool:
        """Aguarda seletor na thread dedicada"""
        self._do_initialize()
        try:
            self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False
    
    def _do_click(self, selector: str):
        """Clica em elemento na thread dedicada"""
        self._do_initialize()
        self._page.click(selector)
    
    def _do_fill(self, selector: str, value: str):
        """Preenche campo na thread dedicada"""
        self._do_initialize()
        self._page.fill(selector, value)
    
    def _do_screenshot(self, path: str):
        """Tira screenshot na thread dedicada"""
        self._do_initialize()
        self._page.screenshot(path=path)
    
    def _do_login(self) -> bool:
        """
        Realiza login no DJI AG usando credenciais do .env
        Retorna True se login bem-sucedido
        """
        self._do_initialize()
        
        email = self._settings.DJI_USERNAME
        password = self._settings.dji_password
        
        if not email or not password:
            raise ValueError("DJI_USERNAME e DJI_PASSWORD devem estar configurados no .env")
        
        # Navegar para records (redireciona para login se nao autenticado)
        self._page.goto("https://www.djiag.com/br/records", timeout=60000, wait_until="networkidle")
        
        # Aguardar estabilizacao da pagina (pode redirecionar)
        time.sleep(5)
        
        current_url = self._page.url
        
        # Se ja esta em /records e nao em /login, ja esta logado
        if "/records" in current_url and "/login" not in current_url:
            return True
        
        # Precisa fazer login
        if "/login" in current_url:
            # Aceitar cookies se aparecer
            try:
                cookies_btn = self._page.locator("button:has-text('Accept'), button:has-text('Aceitar')").first
                if cookies_btn.is_visible(timeout=2000):
                    cookies_btn.click()
                    time.sleep(1)
            except:
                pass
            
            # Procurar checkbox "I have read..."
            try:
                checkbox = self._page.locator("input[type='checkbox']").first
                if checkbox.is_visible(timeout=5000):
                    checkbox.click()
                    time.sleep(1)
            except:
                pass
            
            # Clicar em "Login with DJI account"
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
                    btn = self._page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        clicked = True
                        break
                except:
                    continue
            
            time.sleep(3)
            current_url = self._page.url
        
        # Preencher credenciais no account.dji.com
        if "account.dji.com" in current_url:
            time.sleep(2)
            
            # Email
            try:
                email_field = self._page.locator("input[name='username'], input[type='email'], input[type='text']").first
                if email_field.is_visible(timeout=5000):
                    email_field.click()
                    time.sleep(0.3)
                    email_field.type(email, delay=30)
                    time.sleep(0.5)
            except:
                pass
            
            # Senha
            try:
                pass_field = self._page.locator("input[type='password']").first
                if pass_field.is_visible(timeout=3000):
                    pass_field.click()
                    time.sleep(0.3)
                    pass_field.type(password, delay=30)
                    time.sleep(0.5)
            except:
                pass
            
            # Clicar em Login
            login_selectors = [
                "button[type='submit']",
                "button:has-text('Log in')",
                "button:has-text('Login')",
                "button:has-text('Sign in')",
            ]
            
            for selector in login_selectors:
                try:
                    btn = self._page.locator(selector).first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        break
                except:
                    continue
            
            # Aguardar redirecionamento (ate 60s para CAPTCHA manual)
            for i in range(60):
                time.sleep(1)
                current_url = self._page.url
                if "account.dji.com/login" not in current_url and "account.dji.com/logout" not in current_url:
                    break
        
        # Navegar de volta para records
        time.sleep(2)
        self._page.goto("https://www.djiag.com/br/records", wait_until="networkidle", timeout=60000)
        time.sleep(5)
        
        current_url = self._page.url
        return "/records" in current_url and "/login" not in current_url
    
    def _do_execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Executa funcao arbitraria com acesso a page na thread dedicada"""
        self._do_initialize()
        return func(self._page, self._context, *args, **kwargs)


# Instancia global do PlaywrightThread
_playwright_thread: Optional[PlaywrightThread] = None
_thread_lock = threading.Lock()


def get_playwright_thread() -> PlaywrightThread:
    """Obtem a instancia global do PlaywrightThread"""
    global _playwright_thread
    with _thread_lock:
        if _playwright_thread is None:
            _playwright_thread = PlaywrightThread()
            _playwright_thread.start()
        return _playwright_thread


class BrowserService(IBrowserService):
    """Implementacao do servico de browser usando Playwright sync API"""
    
    def __init__(self):
        self._pw_thread = get_playwright_thread()
    
    async def initialize(self) -> None:
        """Inicializa o browser"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_initialize
        )
    
    async def close(self) -> None:
        """Fecha o browser"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_close
        )
    
    async def is_logged_in(self) -> bool:
        """Verifica se esta logado no DJI AG"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_is_logged_in
        )
    
    async def is_authenticated(self) -> bool:
        """Verifica se esta autenticado (alias para is_logged_in)"""
        return await self.is_logged_in()
    
    async def navigate_to_records(self) -> None:
        """Navega para a pagina de records"""
        await self.navigate("https://www.djiag.com/br/records")
    
    async def navigate(self, url: str) -> str:
        """Navega para uma URL e retorna o conteudo"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_navigate,
            url
        )
    
    async def get_page_content(self) -> str:
        """Obtem o conteudo HTML da pagina atual"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_get_page_content
        )
    
    async def execute_script(self, script: str) -> Any:
        """Executa JavaScript na pagina"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_execute_script,
            script
        )
    
    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> bool:
        """Aguarda um seletor CSS aparecer na pagina"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_wait_for_selector,
            selector,
            timeout
        )
    
    async def click(self, selector: str) -> None:
        """Clica em um elemento"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_click,
            selector
        )
    
    async def fill(self, selector: str, value: str) -> None:
        """Preenche um campo de input"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_fill,
            selector,
            value
        )
    
    async def screenshot(self, path: str) -> None:
        """Tira um screenshot da pagina"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_screenshot,
            path
        )
    
    async def login(self) -> bool:
        """Realiza login no DJI AG usando credenciais do .env"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_login
        )
    
    async def execute_in_browser(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa uma funcao arbitraria no contexto do browser.
        A funcao recebe (page, context, *args, **kwargs) como parametros.
        """
        from functools import partial
        loop = asyncio.get_event_loop()
        
        # Usar partial para passar kwargs corretamente
        wrapped_func = partial(self._pw_thread._do_execute_function, func, *args, **kwargs)
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            wrapped_func
        )


# Funcao helper para executar codigo no browser de forma assincrona
async def execute_in_browser_async(func: Callable, *args, **kwargs) -> Any:
    """
    Helper para executar uma funcao no contexto do browser.
    A funcao recebe (page, context, *args, **kwargs).
    """
    from functools import partial
    pw_thread = get_playwright_thread()
    loop = asyncio.get_event_loop()
    
    # Usar partial para passar kwargs corretamente
    wrapped_func = partial(pw_thread._do_execute_function, func, *args, **kwargs)
    return await loop.run_in_executor(
        None,
        pw_thread.execute,
        wrapped_func
    )


# Alias para compatibilidade com codigo existente
PlaywrightBrowserService = BrowserService
