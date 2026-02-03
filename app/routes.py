from fastapi import APIRouter, HTTPException, Query
from app.services.djiag_service import dji_service
from app.services.djiag_playwright_service import get_playwright_service
from app.models import (
    LoginCredentials,
    SetTokenRequest,
    AuthResponse,
    RecordsListResponse,
    DownloadResponse,
    SessionStatus,
)

router = APIRouter(prefix="/api", tags=["API"])


@router.get("/status", response_model=SessionStatus)
async def get_status():
    """Retorna o status da sessão atual"""
    return get_playwright_service().get_session_status()


@router.post("/auth/login", response_model=AuthResponse)
async def login(credentials: LoginCredentials = None):
    """
    Realiza login automático no DJI Account usando Playwright.
    
    O login é feito automaticamente com as credenciais do .env ou
    as credenciais fornecidas no body da requisição.
    
    Se as credenciais não forem fornecidas, usa as variáveis de ambiente:
    - DJI_USERNAME
    - DJI_PASSWORD
    """
    result = await get_playwright_service().login(credentials)
    
    if not result.success:
        raise HTTPException(status_code=401, detail=result.message)
    
    return result


@router.post("/auth/set-token", response_model=AuthResponse)
async def set_token(request: SetTokenRequest):
    """
    Define o token de autenticação manualmente.
    
    Use este endpoint para testes quando você já tem um token válido
    obtido do browser DevTools (Network tab > Headers > x-auth-token).
    
    **Nota**: A API do DJI AG usa WebAssembly para gerar assinaturas,
    então o endpoint /auth/login é recomendado.
    """
    dji_service.set_auth_token(request.auth_token, request.device_id)
    return AuthResponse(
        success=True,
        message="Token set successfully",
        session_status=dji_service.get_session_status(),
    )


@router.post("/auth/logout")
async def logout():
    """Encerra a sessão"""
    get_playwright_service().close()
    await dji_service.close()
    return {"success": True, "message": "Logged out successfully"}


@router.get("/records", response_model=RecordsListResponse)
async def get_records():
    """
    Retorna a lista de records do TaskHistory.
    
    Requer login prévio via /auth/login
    """
    result = await get_playwright_service().get_records()
    
    if not result.success:
        status_code = 401 if "autenticado" in (result.message or "").lower() or "login" in (result.message or "").lower() else 500
        raise HTTPException(status_code=status_code, detail=result.message)
    
    return result


@router.post("/records/{record_id}/download", response_model=DownloadResponse)
async def download_record(record_id: str):
    """Faz download de um record específico"""
    if not record_id:
        raise HTTPException(status_code=400, detail="Record ID is required")
    
    result = await get_playwright_service().download_record(record_id)
    
    if not result.success:
        status_code = 401 if "autenticado" in result.message.lower() else 500
        raise HTTPException(status_code=status_code, detail=result.message)
    
    return result


@router.post("/records/download-all", response_model=DownloadResponse)
async def download_all():
    """Faz download de todos os records usando o botão Download All"""
    result = await get_playwright_service().download_all()
    
    if not result.success:
        status_code = 401 if "autenticado" in result.message.lower() else 500
        raise HTTPException(status_code=status_code, detail=result.message)
    
    return result
