"""
Use Case: List Records
"""
from dataclasses import dataclass
from typing import List
from ..dtos import RecordListResponse, RecordSummaryDTO
from ...domain.interfaces import IRecordRepository


@dataclass
class ListRecordsInput:
    page: int = 1
    per_page: int = 30


class ListRecordsUseCase:
    """Caso de uso para listar todos os records"""
    
    def __init__(self, record_repository: IRecordRepository):
        self._repository = record_repository
    
    async def execute(self, input_data: ListRecordsInput = None) -> RecordListResponse:
        if input_data is None:
            input_data = ListRecordsInput()
        
        records = await self._repository.list_all(
            page=input_data.page,
            per_page=input_data.per_page
        )
        
        items = [
            RecordSummaryDTO(
                id=r.id,
                takeoff_landing_time=r.takeoff_landing_time,
                flight_duration=r.flight_duration,
                task_mode=r.task_mode,
                area=r.area,
                application_rate=r.application_rate,
                flight_mode=r.flight_mode,
                pilot_name=r.pilot_name,
                device_name=r.device_name,
            )
            for r in records
        ]
        
        return RecordListResponse(
            items=items,
            total=len(items),
            page=input_data.page,
            per_page=input_data.per_page,
        )
