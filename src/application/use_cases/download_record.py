"""
Use Case: Download Record
"""
from dataclasses import dataclass
from typing import Optional
from ..dtos import DownloadResultDTO
from ...domain.interfaces import IRecordRepository


@dataclass
class DownloadRecordInput:
    record_id: str
    include_points: bool = True


class DownloadRecordUseCase:
    """Caso de uso para fazer download de um record completo"""
    
    def __init__(self, record_repository: IRecordRepository):
        self._repository = record_repository
    
    async def execute(self, input_data: DownloadRecordInput) -> Optional[DownloadResultDTO]:
        result = await self._repository.download_record(input_data.record_id)
        
        if not result:
            return None
        
        return DownloadResultDTO(
            record_id=input_data.record_id,
            success=result.get('success', False),
            message=result.get('message'),
            metadata=result.get('metadata'),
            geojson=result.get('geojson') if input_data.include_points else None,
            total_points=result.get('total_points', 0),
        )
