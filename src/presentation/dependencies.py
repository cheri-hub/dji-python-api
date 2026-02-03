"""
Dependency Injection
"""
from functools import lru_cache
from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

from ..infrastructure.services import PlaywrightBrowserService
from ..infrastructure.repositories import DjiAgRecordRepository
from ..infrastructure.config import get_settings
from ..application.use_cases import (
    ListRecordsUseCase,
    GetRecordUseCase,
    DownloadRecordUseCase,
    GetFlightDataUseCase,
)


# ============================================================
# API Key Security
# ============================================================

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Valida o header X-API-KEY.
    Lança HTTPException 401 se inválido.
    """
    settings = get_settings()
    
    if not settings.api_key:
        raise HTTPException(
            status_code=500,
            detail="API_KEY não configurada no servidor. Configure a variável de ambiente API_KEY."
        )
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Header X-API-KEY é obrigatório",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="X-API-KEY inválida",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key


# Singleton para browser service
_browser_service = None


def get_browser_service() -> PlaywrightBrowserService:
    global _browser_service
    if _browser_service is None:
        _browser_service = PlaywrightBrowserService()
    return _browser_service


def get_record_repository() -> DjiAgRecordRepository:
    browser = get_browser_service()
    return DjiAgRecordRepository(browser)


def get_list_records_use_case() -> ListRecordsUseCase:
    repository = get_record_repository()
    return ListRecordsUseCase(repository)


def get_record_use_case() -> GetRecordUseCase:
    repository = get_record_repository()
    return GetRecordUseCase(repository)


def get_download_record_use_case() -> DownloadRecordUseCase:
    repository = get_record_repository()
    return DownloadRecordUseCase(repository)


def get_flight_data_use_case() -> GetFlightDataUseCase:
    repository = get_record_repository()
    return GetFlightDataUseCase(repository)
