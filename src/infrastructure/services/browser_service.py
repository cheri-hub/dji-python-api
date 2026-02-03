"""
Playwright Browser Service - Usando sync API em thread dedicada

NOTA: Usa API síncrona do Playwright executada em uma única thread dedicada
para garantir compatibilidade e evitar problemas de threading.
Todas as operações do Playwright DEVEM rodar na mesma thread
onde o browser foi inicializado. Esta classe garante isso.
"""
import asyncio
import threading
import queue
from functools import partial
from typing import Optional, Any, Callable
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from ...domain.interfaces import IBrowserService
from ..config import get_settings


class PlaywrightThread:
    """
    Thread dedicada para todas as operações do Playwright.
    Playwright requer que todas as operações sejam feitas na mesma thread
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
        """Executa uma função na thread dedicada e retorna o resultado"""
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
            # Verifica se o browser ainda está ativo
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
        
        # Lança o browser com contexto persistente
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self._settings.BROWSER_PROFILE_DIR,
            headless=self._settings.BROWSER_HEADLESS,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Usa a primeira página ou cria uma nova
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()
    
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
            self._page.goto(self._settings.DJIAG_BASE_URL, wait_until="networkidle", timeout=30000)
            
            # Verifica se há elemento de usuário logado
            user_element = self._page.query_selector('.user-name, .user-info, [class*="user"]')
            if user_element:
                return True
            
            # Verifica se está na página de login
            login_form = self._page.query_selector('input[type="password"], .login-form')
            if login_form:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _do_navigate(self, url: str) -> str:
        """Navega para uma URL na thread dedicada"""
        self._do_initialize()
        self._page.goto(url, wait_until="networkidle", timeout=60000)
        return self._page.content()
    
    def _do_get_page_content(self) -> str:
        """Obtém conteúdo da página na thread dedicada"""
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
    
    def _do_execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Executa função arbitrária com acesso à page na thread dedicada"""
        self._do_initialize()
        return func(self._page, self._context, *args, **kwargs)


# Instância global do PlaywrightThread
_playwright_thread: Optional[PlaywrightThread] = None
_thread_lock = threading.Lock()


def get_playwright_thread() -> PlaywrightThread:
    """Obtém a instância global do PlaywrightThread"""
    global _playwright_thread
    with _thread_lock:
        if _playwright_thread is None:
            _playwright_thread = PlaywrightThread()
            _playwright_thread.start()
        return _playwright_thread


class BrowserService(IBrowserService):
    """Implementação do serviço de browser usando Playwright sync API"""
    
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
        """Verifica se está logado no DJI AG"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_is_logged_in
        )
    
    async def navigate(self, url: str) -> str:
        """Navega para uma URL e retorna o conteúdo"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_navigate,
            url
        )
    
    async def get_page_content(self) -> str:
        """Obtém o conteúdo HTML da página atual"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_get_page_content
        )
    
    async def execute_script(self, script: str) -> Any:
        """Executa JavaScript na página"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_execute_script,
            script
        )
    
    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> bool:
        """Aguarda um seletor CSS aparecer na página"""
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
        """Tira um screenshot da página"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_screenshot,
            path
        )
    
    async def execute_in_browser(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa uma função arbitrária no contexto do browser.
        A função recebe (page, context, *args, **kwargs) como parâmetros.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._pw_thread.execute,
            self._pw_thread._do_execute_function,
            func,
            *args,
            **kwargs
        )


# Função helper para executar código no browser de forma assíncrona
async def execute_in_browser_async(func: Callable, *args, **kwargs) -> Any:
    """
    Helper para executar uma função no contexto do browser.
    A função recebe (page, context, *args, **kwargs).
    """
    pw_thread = get_playwright_thread()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        pw_thread.execute,
        pw_thread._do_execute_function,
        func,
        *args,
        **kwargs
    )


# Alias para compatibilidade com código existente
PlaywrightBrowserService = BrowserService
