"""
Domain Interfaces - Repository Contracts
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities import Record, RecordSummary, FlightData


class IRecordRepository(ABC):
    """Interface para repositório de Records"""
    
    @abstractmethod
    async def list_all(self, page: int = 1, per_page: int = 30) -> List[RecordSummary]:
        """Lista todos os records com paginação"""
        pass
    
    @abstractmethod
    async def get_by_id(self, record_id: str) -> Optional[Record]:
        """Busca um record pelo ID"""
        pass
    
    @abstractmethod
    async def get_flight_data(self, record_id: str) -> Optional[FlightData]:
        """Busca os dados de voo de um record"""
        pass
    
    @abstractmethod
    async def download_record(self, record_id: str) -> Optional[dict]:
        """Faz download completo de um record (metadata + flight data)"""
        pass


class IBrowserService(ABC):
    """Interface para serviço de browser (Playwright)"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Inicializa o browser"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Fecha o browser"""
        pass
    
    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Verifica se está autenticado"""
        pass
    
    @abstractmethod
    async def login(self, email: str, password: str) -> bool:
        """Faz login no DJI AG"""
        pass
    
    @abstractmethod
    async def navigate_to_records(self) -> None:
        """Navega para a página de records"""
        pass
