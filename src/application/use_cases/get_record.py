"""
Use Case: Get Record Details
"""
from dataclasses import dataclass
from typing import Optional
from ..dtos import RecordDetailDTO
from ...domain.interfaces import IRecordRepository


@dataclass
class GetRecordInput:
    record_id: str


class GetRecordUseCase:
    """Caso de uso para buscar detalhes de um record"""
    
    def __init__(self, record_repository: IRecordRepository):
        self._repository = record_repository
    
    async def execute(self, input_data: GetRecordInput) -> Optional[RecordDetailDTO]:
        record = await self._repository.get_by_id(input_data.record_id)
        
        if not record:
            return None
        
        return RecordDetailDTO(
            id=record.id,
            serial_number=record.serial_number,
            hardware_id=record.hardware_id,
            start_timestamp=record.start_timestamp,
            end_timestamp=record.end_timestamp,
            start_datetime=record.start_datetime.isoformat() if record.start_datetime else None,
            end_datetime=record.end_datetime.isoformat() if record.end_datetime else None,
            duration_seconds=record.duration_seconds,
            duration_minutes=record.duration_minutes,
            create_date=record.create_date,
            location=record.location,
            drone_type=record.drone_type,
            nickname=record.nickname,
            app_version=record.app_version,
            nozzle_type=record.nozzle_type,
            flyer_name=record.flyer_name,
            team_name=record.team_name,
            radar_height=record.radar_height,
            max_radar_height=record.max_radar_height,
            work_speed=record.work_speed,
            max_flight_speed=record.max_flight_speed,
            spray_width=record.spray_width,
            work_area_m2=record.new_work_area,
            work_area_ha=record.work_area_ha,
            spray_usage_ml=record.spray_usage,
            spray_usage_liters=record.spray_usage_liters,
            manual_mode=record.manual_mode,
            use_rtk=record.use_rtk,
        )
