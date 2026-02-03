"""
Dependency Injection
"""
from functools import lru_cache

from ..infrastructure.services import PlaywrightBrowserService
from ..infrastructure.repositories import DjiAgRecordRepository
from ..application.use_cases import (
    ListRecordsUseCase,
    GetRecordUseCase,
    DownloadRecordUseCase,
    GetFlightDataUseCase,
)


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
