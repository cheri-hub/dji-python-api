"""
Auth Routes - Login
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_browser_service
from ...infrastructure.services import PlaywrightBrowserService

router = APIRouter(prefix="/auth")


class LoginResponse(BaseModel):
    success: bool
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(
    browser: PlaywrightBrowserService = Depends(get_browser_service),
):
    """
    Realiza login no DJI AG SmartFarm.
    
    Autentica e mantém sessão para operações subsequentes.
    
    **Nota**: Se aparecer CAPTCHA, complete-o manualmente no browser.
    O login aguardará até 30 segundos para conclusão.
    """
    try:
        success = await browser.login()
        
        if success:
            return LoginResponse(success=True, message="Login realizado com sucesso")
        else:
            raise HTTPException(status_code=401, detail="Falha no login. Verifique credenciais ou complete o CAPTCHA.")
    except HTTPException:
        raise  # Re-raise HTTPException sem modificar
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@router.get("/status")
async def auth_status(
    browser: PlaywrightBrowserService = Depends(get_browser_service),
):
    """
    Verifica status da autenticação.
    
    Navega para a página de records e verifica se está logado.
    """
    try:
        is_authenticated = await browser.is_authenticated()
        return {"authenticated": is_authenticated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro verificando autenticação: {str(e)}")
