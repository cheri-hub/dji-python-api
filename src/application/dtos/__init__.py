"""
Application DTOs - Data Transfer Objects
"""
from dataclasses import dataclass
from typing import List, Optional, Any


@dataclass
class RecordSummaryDTO:
    """DTO para resumo de record"""
    id: str
    takeoff_landing_time: str
    flight_duration: str
    task_mode: str
    area: str
    application_rate: str
    flight_mode: str
    pilot_name: str
    device_name: str


@dataclass
class RecordListResponse:
    """DTO para resposta de listagem"""
    items: List[RecordSummaryDTO]
    total: int
    page: int
    per_page: int


@dataclass
class RecordDetailDTO:
    """DTO para detalhes completos de um record"""
    id: str
    serial_number: Optional[str] = None
    hardware_id: Optional[str] = None
    start_timestamp: Optional[int] = None
    end_timestamp: Optional[int] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    duration_seconds: Optional[int] = None
    duration_minutes: Optional[float] = None
    create_date: Optional[str] = None
    location: Optional[str] = None
    drone_type: Optional[str] = None
    nickname: Optional[str] = None
    app_version: Optional[str] = None
    nozzle_type: Optional[int] = None
    flyer_name: Optional[str] = None
    team_name: Optional[str] = None
    radar_height: Optional[float] = None
    max_radar_height: Optional[float] = None
    work_speed: Optional[float] = None
    max_flight_speed: Optional[float] = None
    spray_width: Optional[float] = None
    work_area_m2: Optional[float] = None
    work_area_ha: Optional[float] = None
    spray_usage_ml: Optional[float] = None
    spray_usage_liters: Optional[float] = None
    manual_mode: Optional[bool] = None
    use_rtk: Optional[bool] = None


@dataclass
class GpsPointDTO:
    """DTO para ponto GPS"""
    index: int
    latitude: float
    longitude: float
    heading: Optional[float] = None
    velocity_x: Optional[float] = None
    velocity_y: Optional[float] = None
    spray_rate: Optional[float] = None
    speed_ms: Optional[float] = None


@dataclass
class FlightDataDTO:
    """DTO para dados de voo"""
    record_id: str
    total_points: int
    bounds: Optional[dict] = None
    telemetry: Optional[dict] = None
    points: Optional[List[GpsPointDTO]] = None
    geojson: Optional[dict] = None


@dataclass
class DownloadResultDTO:
    """DTO para resultado de download"""
    record_id: str
    success: bool
    message: Optional[str] = None
    metadata: Optional[dict] = None
    geojson: Optional[dict] = None
    total_points: int = 0
