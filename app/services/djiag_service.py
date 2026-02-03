import httpx
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import re
import time
import hashlib
import hmac
import base64
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, parse_qs, urlparse

from app.config import settings
from app.models import (
    Record,
    RecordsListResponse,
    DownloadResponse,
    SessionStatus,
    LoginCredentials,
    AuthResponse,
)


class DJIAgService:
    """Serviço para DJI AG usando requisições HTTP diretas"""
    
    # API base URL (Korea region - pode variar)
    API_BASE = "https://kr-ag2-api.dji.com/api/web/v1"
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._is_authenticated: bool = False
        self._current_username: str = ""
        self._auth_token: Optional[str] = None
        self._sign_key: Optional[str] = None  # Chave extraída do JWT para assinatura
        self._device_id: str = "web-12345"  # Usar device-id fixo como no browser
    
    def _extract_sign_key_from_jwt(self, token: str) -> Optional[str]:
        """Extrai a chave de assinatura do payload do JWT"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            
            payload = parts[1]
            # Adicionar padding para base64
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload = payload + ("=" * padding)
            
            # Decodificar base64url para base64
            payload = payload.replace("-", "+").replace("_", "/")
            decoded = base64.b64decode(payload).decode("utf-8")
            data = json.loads(decoded)
            
            # O sub contém: "user_id,platform,timestamp,secret_key"
            sub = data.get("sub", "")
            parts = sub.split(",")
            if len(parts) >= 4:
                # A última parte é a chave secreta
                return parts[3]
            return None
        except Exception as e:
            print(f"   Warning: Could not extract sign key from JWT: {e}")
            return None
    
    def _generate_signature(self, method: str, path: str, x_ag_date: str) -> str:
        """Gera a assinatura HMAC-SHA256 para a requisição"""
        if not self._sign_key:
            return ""
        
        try:
            # O conteúdo a assinar é: method + path + date
            # Path inclui a query string
            sign_content = f"{method}{path}{x_ag_date}"
            
            signature = hmac.new(
                self._sign_key.encode('utf-8'),
                sign_content.encode('utf-8'),
                hashlib.sha256
            )
            # Retornar em base64
            return base64.b64encode(signature.digest()).decode('utf-8')
        except Exception as e:
            print(f"   Warning: Could not generate signature: {e}")
            return ""
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna ou cria o cliente HTTP"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin": "https://www.djiag.com",
                    "Referer": "https://www.djiag.com/",
                },
            )
        return self._client
    
    def _get_api_headers(self, method: str = "GET", path: str = "") -> Dict[str, str]:
        """Retorna headers para a API do DJI AG"""
        x_ag_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}Z"
        x_request_id = str(uuid.uuid4())
        
        headers = {
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh",
            "Origin": "https://www.djiag.com",
            "Referer": "https://www.djiag.com/",
            "device-id": self._device_id,
            "x-new-version": "true",
            "x-request-id": x_request_id,
            "x-ag-date": x_ag_date,
        }
        
        if self._auth_token:
            headers["x-auth-token"] = self._auth_token
            
            # Gerar signature usando a chave extraída do JWT
            if self._sign_key and path:
                signature = self._generate_signature(method, path, x_ag_date)
                if signature:
                    headers["signature"] = signature
                    print(f"   Generated signature for {method} {path[:50]}...")
        
        return headers
    
    def set_auth_token(self, auth_token: str, device_id: Optional[str] = None) -> None:
        """Define o token de autenticação manualmente (para debug/testes)"""
        self._auth_token = auth_token
        # Extrair a chave de assinatura do JWT
        self._sign_key = self._extract_sign_key_from_jwt(auth_token)
        if self._sign_key:
            print(f"   ✓ Extracted sign key: {self._sign_key[:30]}...")
        if device_id:
            self._device_id = device_id
        self._is_authenticated = True
        self._current_username = "manual_token_user"
        print(f"✅ Auth token set manually: {auth_token[:50]}...")
    
    async def close(self) -> None:
        """Fecha o cliente HTTP"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self._is_authenticated = False
        self._current_username = ""
        self._auth_token = None
        print("🔒 HTTP client closed")
    
    async def login(self, credentials: Optional[LoginCredentials] = None) -> AuthResponse:
        """Realiza login no DJI Account via HTTP"""
        try:
            username = credentials.username if credentials and credentials.username else settings.dji_username
            password = credentials.password if credentials and credentials.password else settings.dji_password
            
            if not username or not password:
                return AuthResponse(
                    success=False,
                    message="Credentials not provided. Set DJI_USERNAME and DJI_PASSWORD in .env or pass them in the request.",
                )
            
            client = await self._get_client()
            
            print("🔐 Starting login process...")
            
            # Passo 1: Acessar página de login do djiag.com para pegar cookies iniciais
            print("   Step 1: Getting initial cookies from djiag.com...")
            resp = await client.get("https://www.djiag.com/login")
            print(f"   Status: {resp.status_code}")
            
            # Passo 2: Acessar página de login do DJI Account
            print("   Step 2: Accessing DJI Account login page...")
            login_url = "https://account.dji.com/login"
            params = {
                "backUrl": "https://www.djiag.com",
                "appId": "dji-ag-auth-oversea"
            }
            resp = await client.get(login_url, params=params)
            print(f"   Status: {resp.status_code}")
            
            # Extrair CSRF token ou outros parâmetros do formulário
            html = resp.text
            csrf_token = None
            
            # Procurar por tokens CSRF no HTML
            csrf_patterns = [
                r'name="_csrf"\s+value="([^"]+)"',
                r'name="csrf_token"\s+value="([^"]+)"',
                r'"csrfToken":\s*"([^"]+)"',
                r'_csrf=([^&"]+)',
            ]
            for pattern in csrf_patterns:
                match = re.search(pattern, html)
                if match:
                    csrf_token = match.group(1)
                    print(f"   Found CSRF token: {csrf_token[:20]}...")
                    break
            
            # Passo 3: Fazer POST do login
            print("   Step 3: Submitting login credentials...")
            
            # Tentar diferentes endpoints de login do DJI
            login_endpoints = [
                "https://account.dji.com/api/v2/login",
                "https://account.dji.com/api/login",
                "https://account.dji.com/login",
            ]
            
            login_data = {
                "username": username,
                "password": password,
                "appId": "dji-ag-auth-oversea",
            }
            
            if csrf_token:
                login_data["_csrf"] = csrf_token
            
            login_success = False
            
            for endpoint in login_endpoints:
                try:
                    print(f"   Trying endpoint: {endpoint}")
                    
                    # Tentar como JSON
                    resp = await client.post(
                        endpoint,
                        json=login_data,
                        headers={
                            "Content-Type": "application/json",
                            "Referer": "https://account.dji.com/login",
                            "Origin": "https://account.dji.com",
                        }
                    )
                    
                    print(f"   Status: {resp.status_code}")
                    
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            print(f"   Response: {json.dumps(data, indent=2)[:500]}")
                            
                            if data.get("success") or data.get("code") == 0 or "token" in data:
                                login_success = True
                                print("   ✓ Login API returned success")
                                break
                        except:
                            pass
                    
                    # Tentar como form data
                    resp = await client.post(
                        endpoint,
                        data=login_data,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Referer": "https://account.dji.com/login",
                        }
                    )
                    
                    print(f"   Form Status: {resp.status_code}")
                    
                    if resp.status_code in [200, 302]:
                        # Verificar se houve redirecionamento ou se recebemos cookies
                        if resp.cookies or "djiag" in str(resp.url):
                            login_success = True
                            print("   ✓ Login via form successful")
                            break
                            
                except Exception as e:
                    print(f"   Error with {endpoint}: {e}")
                    continue
            
            # Passo 4: Verificar autenticação acessando djiag.com/records
            print("   Step 4: Verifying authentication and getting auth token...")
            resp = await client.get("https://www.djiag.com/records")
            print(f"   Records page status: {resp.status_code}")
            print(f"   Final URL: {resp.url}")
            
            # Salvar HTML para debug
            html = resp.text
            debug_html_path = settings.get_download_path() / "debug_records_page.html"
            with open(debug_html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"   Saved HTML to: {debug_html_path}")
            
            # Procurar pelo token de autenticação no HTML (expandido)
            token_patterns = [
                r'"token"\s*:\s*"([^"]+)"',
                r'"authToken"\s*:\s*"([^"]+)"',
                r'"x-auth-token"\s*:\s*"([^"]+)"',
                r'accessToken["\']?\s*[:=]\s*["\']([^"\']+)',
                r'"jwt"\s*:\s*"([^"]+)"',
                r'"access_token"\s*:\s*"([^"]+)"',
                r'"userToken"\s*:\s*"([^"]+)"',
                r'__NUXT__.*?"token"\s*:\s*"([^"]+)"',
                r'window\.__INITIAL_STATE__.*?"token"\s*:\s*"([^"]+)"',
            ]
            
            for pattern in token_patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    potential_token = match.group(1)
                    # JWT tokens começam com "eyJ"
                    if potential_token.startswith("eyJ") or len(potential_token) > 100:
                        self._auth_token = potential_token
                        print(f"   ✓ Found auth token in HTML: {self._auth_token[:50]}...")
                        break
            
            # Verificar cookies
            print("   Checking cookies...")
            for cookie in client.cookies.jar:
                cookie_val = cookie.value[:50] if len(cookie.value) > 50 else cookie.value
                print(f"   Cookie: {cookie.name}={cookie_val}...")
                
                # Procurar por tokens em cookies
                if "token" in cookie.name.lower() or "auth" in cookie.name.lower() or "jwt" in cookie.name.lower():
                    self._auth_token = cookie.value
                    print(f"   ✓ Found auth token in cookie: {cookie.name}")
                
                # Também verificar cookies que começam com "eyJ" (JWT)
                if cookie.value.startswith("eyJ"):
                    self._auth_token = cookie.value
                    print(f"   ✓ Found JWT token in cookie: {cookie.name}")
            
            # Verificar headers de resposta
            for header_name, header_value in resp.headers.items():
                if "token" in header_name.lower() or "auth" in header_name.lower():
                    print(f"   Header: {header_name}={header_value[:50] if len(header_value) > 50 else header_value}")
                    if header_value.startswith("eyJ"):
                        self._auth_token = header_value
                        print(f"   ✓ Found token in header: {header_name}")
            
            if "records" in str(resp.url) and "login" not in str(resp.url):
                self._is_authenticated = True
                self._current_username = username
                
                if self._auth_token:
                    print("✅ Login successful with auth token!")
                else:
                    print("✅ Login successful (no token found, may need to extract from page)")
                
                return AuthResponse(
                    success=True,
                    message="Login successful",
                    session_status=self.get_session_status(),
                )
            
            # Se não funcionou, salvar resposta para debug
            debug_path = settings.get_download_path() / "debug_login_response.html"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"   Debug HTML saved to: {debug_path}")
            
            return AuthResponse(
                success=False,
                message="Login failed. The DJI authentication flow may require browser interaction (CAPTCHA, 2FA). Check debug_login_response.html for details.",
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
        """Obtém a lista de records do TaskHistory"""
        try:
            if not self._is_authenticated:
                return RecordsListResponse(
                    success=False,
                    message="Not authenticated. Please login first.",
                )
            
            client = await self._get_client()
            
            print("📋 Fetching records list...")
            
            # Calcular timestamps para os últimos 30 dias
            now = int(time.time() * 1000)
            thirty_days_ago = now - (30 * 24 * 60 * 60 * 1000)
            
            # Construir path com query string (necessário para assinatura)
            path = f"/api/web/v1/flight_records?filters%5Btimestamp_gteq%5D={thirty_days_ago}&filters%5Btimestamp_lteq%5D={now}&page_size=30&page=1"
            api_url = f"https://kr-ag2-api.dji.com{path}"
            
            headers = self._get_api_headers("GET", path)
            
            print(f"   API URL: {api_url}")
            print(f"   Auth Token: {self._auth_token[:50] if self._auth_token else 'None'}...")
            print(f"   Sign Key: {self._sign_key[:30] if self._sign_key else 'None'}...")
            
            resp = await client.get(api_url, headers=headers)
            print(f"   Status: {resp.status_code}")
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"   Response keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
                    
                    # Salvar para debug
                    debug_path = settings.get_download_path() / "debug_flight_records.json"
                    with open(debug_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"   Saved to: {debug_path}")
                    
                    # Extrair records
                    records_data = data.get("data", data.get("records", data.get("list", data.get("items", []))))
                    
                    if isinstance(records_data, list):
                        records = []
                        for r in records_data:
                            record_id = str(r.get("id", r.get("flight_record_id", r.get("record_id", ""))))
                            records.append(Record(
                                id=record_id,
                                name=r.get("name", r.get("task_name", f"Flight {record_id}")),
                                date=r.get("date", r.get("takeoff_time", r.get("created_at", ""))),
                                status=str(r.get("status", "")),
                                type=r.get("type", r.get("task_mode", "Spray")),
                                url=f"https://www.djiag.com/record/{record_id}",
                            ))
                        
                        print(f"✅ Found {len(records)} records")
                        return RecordsListResponse(
                            success=True,
                            records=records,
                            total=len(records),
                        )
                except Exception as e:
                    print(f"   Error parsing JSON: {e}")
            
            # Fallback: parsear HTML da página
            print("   Falling back to HTML parsing...")
            resp = await client.get("https://www.djiag.com/records")
            html = resp.text
            
            debug_path = settings.get_download_path() / "debug_records_page.html"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html)
            
            records = []
            record_pattern = r'/record/(\d+)'
            record_ids = list(set(re.findall(record_pattern, html)))
            
            for record_id in record_ids:
                records.append(Record(
                    id=record_id,
                    name=f"Record {record_id}",
                    url=f"https://www.djiag.com/record/{record_id}",
                ))
            
            print(f"   Found {len(records)} records from HTML")
            
            return RecordsListResponse(
                success=True,
                records=records,
                total=len(records),
                message="Retrieved from HTML (API may require signature)" if not records else None,
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
        """Faz download de um record específico"""
        try:
            if not self._is_authenticated:
                return DownloadResponse(
                    success=False,
                    message="Not authenticated. Please login first.",
                )
            
            client = await self._get_client()
            
            print(f"📥 Downloading record: {record_id}")
            
            # Tentar endpoints de download (incluindo API real)
            download_endpoints = [
                f"/api/web/v1/flight_records/{record_id}/download",
                f"/api/web/v1/flight_records/{record_id}/export",
            ]
            
            for path in download_endpoints:
                try:
                    endpoint = f"https://kr-ag2-api.dji.com{path}"
                    headers = self._get_api_headers("GET", path)
                    print(f"   Trying: {endpoint}")
                    resp = await client.get(endpoint, headers=headers)
                    print(f"   Status: {resp.status_code}")
                    
                    if resp.status_code == 200:
                        content_type = resp.headers.get("content-type", "")
                        print(f"   Content-Type: {content_type}")
                        
                        # Se é um arquivo
                        if "application" in content_type or "octet-stream" in content_type or "zip" in content_type:
                            # Extrair nome do arquivo
                            content_disp = resp.headers.get("content-disposition", "")
                            filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disp)
                            filename = filename_match.group(1).strip('"\'') if filename_match else f"record_{record_id}.zip"
                            
                            # Salvar arquivo
                            file_path = settings.get_download_path() / filename
                            with open(file_path, "wb") as f:
                                f.write(resp.content)
                            
                            print(f"✅ Downloaded: {filename} ({len(resp.content)} bytes)")
                            
                            return DownloadResponse(
                                success=True,
                                message="Download completed successfully",
                                file_path=str(file_path),
                                file_name=filename,
                            )
                        
                        # Se é JSON com URL de download
                        try:
                            data = resp.json()
                            print(f"   JSON response: {json.dumps(data, indent=2)[:300]}")
                            download_url = data.get("url", data.get("downloadUrl", data.get("download_url")))
                            if not download_url and isinstance(data.get("data"), dict):
                                download_url = data["data"].get("url", data["data"].get("download_url"))
                            
                            if download_url:
                                print(f"   Downloading from URL: {download_url[:100]}...")
                                resp2 = await client.get(download_url, headers=headers)
                                
                                content_disp = resp2.headers.get("content-disposition", "")
                                filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disp)
                                filename = filename_match.group(1).strip('"\'') if filename_match else f"record_{record_id}.zip"
                                
                                file_path = settings.get_download_path() / filename
                                with open(file_path, "wb") as f:
                                    f.write(resp2.content)
                                
                                print(f"✅ Downloaded: {filename} ({len(resp2.content)} bytes)")
                                return DownloadResponse(
                                    success=True,
                                    message="Download completed successfully",
                                    file_path=str(file_path),
                                    file_name=filename,
                                )
                        except json.JSONDecodeError:
                            pass
                            
                except Exception as e:
                    print(f"   Error: {e}")
                    continue
            
            return DownloadResponse(
                success=False,
                message=f"Could not find download endpoint for record {record_id}.",
            )
        
        except Exception as e:
            print(f"❌ Download error: {e}")
            return DownloadResponse(
                success=False,
                message=f"Download error: {str(e)}",
            )
    
    async def download_all(self) -> DownloadResponse:
        """Faz download de todos os records"""
        try:
            if not self._is_authenticated:
                return DownloadResponse(
                    success=False,
                    message="Not authenticated. Please login first.",
                )
            
            client = await self._get_client()
            
            print("📥 Downloading all records...")
            
            # Calcular timestamps para os últimos 30 dias
            now = int(time.time() * 1000)
            thirty_days_ago = now - (30 * 24 * 60 * 60 * 1000)
            
            # Tentar endpoints de download all (incluindo API real)
            download_paths = [
                f"/api/web/v1/flight_records/export?filters%5Btimestamp_gteq%5D={thirty_days_ago}&filters%5Btimestamp_lteq%5D={now}",
                f"/api/web/v1/flight_records/download?filters%5Btimestamp_gteq%5D={thirty_days_ago}&filters%5Btimestamp_lteq%5D={now}",
            ]
            
            for path in download_paths:
                try:
                    endpoint = f"https://kr-ag2-api.dji.com{path}"
                    headers = self._get_api_headers("GET", path)
                    print(f"   Trying: {endpoint}")
                    resp = await client.get(endpoint, headers=headers)
                    print(f"   Status: {resp.status_code}")
                    
                    if resp.status_code == 200:
                        content_type = resp.headers.get("content-type", "")
                        print(f"   Content-Type: {content_type}")
                        
                        if "application" in content_type or "octet-stream" in content_type or "zip" in content_type:
                            filename = f"all_records_{int(time.time())}.zip"
                            file_path = settings.get_download_path() / filename
                            
                            with open(file_path, "wb") as f:
                                f.write(resp.content)
                            
                            print(f"✅ Downloaded: {filename} ({len(resp.content)} bytes)")
                            
                            return DownloadResponse(
                                success=True,
                                message="Download All completed successfully",
                                file_path=str(file_path),
                                file_name=filename,
                            )
                        
                        # Verificar se é JSON com URL
                        try:
                            data = resp.json()
                            print(f"   JSON response: {json.dumps(data, indent=2)[:300]}")
                            download_url = data.get("url", data.get("downloadUrl", data.get("download_url")))
                            if not download_url and isinstance(data.get("data"), dict):
                                download_url = data["data"].get("url", data["data"].get("download_url"))
                            
                            if download_url:
                                print(f"   Downloading from URL: {download_url[:100]}...")
                                resp2 = await client.get(download_url, headers=headers)
                                filename = f"all_records_{int(time.time())}.zip"
                                file_path = settings.get_download_path() / filename
                                with open(file_path, "wb") as f:
                                    f.write(resp2.content)
                                
                                print(f"✅ Downloaded: {filename} ({len(resp2.content)} bytes)")
                                return DownloadResponse(
                                    success=True,
                                    message="Download All completed successfully",
                                    file_path=str(file_path),
                                    file_name=filename,
                                )
                        except json.JSONDecodeError:
                            pass
                            
                except Exception as e:
                    print(f"   Error: {e}")
                    continue
            
            # Fallback: baixar records individualmente
            print("   Trying to download records individually...")
            records_resp = await self.get_records()
            
            if records_resp.success and records_resp.records:
                downloaded = []
                failed = []
                
                for record in records_resp.records:
                    result = await self.download_record(record.id)
                    if result.success:
                        downloaded.append(record.id)
                    else:
                        failed.append(record.id)
                
                if downloaded:
                    return DownloadResponse(
                        success=True,
                        message=f"Downloaded {len(downloaded)} records individually. Failed: {len(failed)}",
                        file_path=str(settings.get_download_path()),
                    )
            
            return DownloadResponse(
                success=False,
                message="Could not find download-all endpoint. Try downloading records individually.",
            )
        
        except Exception as e:
            print(f"❌ Download All error: {e}")
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
dji_service = DJIAgService()
