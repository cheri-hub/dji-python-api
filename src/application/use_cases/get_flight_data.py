"""
Use Case: Get Flight Data
"""
from dataclasses import dataclass
from typing import Optional
from ..dtos import FlightDataDTO, GpsPointDTO
from ...domain.interfaces import IRecordRepository


@dataclass
class GetFlightDataInput:
    record_id: str
    include_points: bool = True
    format: str = "json"  # json, geojson


class GetFlightDataUseCase:
    """Caso de uso para buscar dados de voo"""
    
    def __init__(self, record_repository: IRecordRepository):
        self._repository = record_repository
    
    async def execute(self, input_data: GetFlightDataInput) -> Optional[FlightDataDTO]:
        flight_data = await self._repository.get_flight_data(input_data.record_id)
        
        if not flight_data:
            return None
        
        # Calcular bounds e telemetry
        flight_data.calculate_bounds()
        flight_data.calculate_telemetry()
        
        points = None
        if input_data.include_points:
            points = [
                GpsPointDTO(
                    index=p.index,
                    latitude=p.latitude,
                    longitude=p.longitude,
                    heading=p.heading,
                    velocity_x=p.velocity_x,
                    velocity_y=p.velocity_y,
                    spray_rate=p.spray_rate,
                    speed_ms=p.speed_ms,
                )
                for p in flight_data.points
            ]
        
        # Se formato é GeoJSON, retornar diretamente
        geojson = None
        if input_data.format == "geojson":
            record = await self._repository.get_by_id(input_data.record_id)
            geojson = flight_data.to_geojson(record)
        
        return FlightDataDTO(
            record_id=flight_data.record_id,
            total_points=flight_data.total_points,
            bounds={
                "lat_min": flight_data.bounds.lat_min,
                "lat_max": flight_data.bounds.lat_max,
                "lon_min": flight_data.bounds.lon_min,
                "lon_max": flight_data.bounds.lon_max,
                "center_lat": flight_data.bounds.center_lat,
                "center_lon": flight_data.bounds.center_lon,
            } if flight_data.bounds else None,
            telemetry={
                "heading_avg": flight_data.telemetry.heading_avg,
                "speed_avg_ms": flight_data.telemetry.speed_avg_ms,
                "speed_max_ms": flight_data.telemetry.speed_max_ms,
                "spray_rate_avg": flight_data.telemetry.spray_rate_avg,
            } if flight_data.telemetry else None,
            points=points,
            geojson=geojson,
        )
