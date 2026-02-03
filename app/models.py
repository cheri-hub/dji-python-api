from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Record(BaseModel):
    """Representa um record da lista de TaskHistory"""
    id: str
    name: str
    date: str = ""
    status: str = ""
    type: str = ""
    url: str = ""
    download_url: Optional[str] = None


class RecordsListResponse(BaseModel):
    """Resposta da listagem de records"""
    success: bool
    records: List[Record] = []
    total: int = 0
    page: Optional[int] = None
    page_size: Optional[int] = None
    message: Optional[str] = None


class DownloadResponse(BaseModel):
    """Resposta de download"""
    success: bool
    message: str
    file_path: Optional[str] = None
    file_name: Optional[str] = None


class SessionStatus(BaseModel):
    """Status da sessão"""
    is_authenticated: bool
    username: Optional[str] = None
    expires_at: Optional[datetime] = None


class LoginCredentials(BaseModel):
    """Credenciais de login"""
    username: Optional[str] = None
    password: Optional[str] = None


class SetTokenRequest(BaseModel):
    """Request para definir o token manualmente"""
    auth_token: str
    device_id: Optional[str] = None
    # Note: A assinatura é gerada por WebAssembly no frontend DJI
    # Não é possível replicá-la facilmente em Python


class AuthResponse(BaseModel):
    """Resposta de autenticação"""
    success: bool
    message: str
    session_status: Optional[SessionStatus] = None


class HealthResponse(BaseModel):
    """Resposta do health check"""
    status: str
    timestamp: datetime
    session: SessionStatus
