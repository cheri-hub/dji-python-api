"""
Domain Entity: Record (Flight Record)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RecordSummary:
    """Resumo de um record (lista)"""
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
class Record:
    """Entidade completa de um Flight Record"""
    id: str
    serial_number: Optional[str] = None
    hardware_id: Optional[str] = None
    
    # Timestamps
    start_timestamp: Optional[int] = None
    end_timestamp: Optional[int] = None
    create_date: Optional[str] = None
    
    # Location
    location: Optional[str] = None
    
    # Equipment
    drone_type: Optional[str] = None
    nickname: Optional[str] = None
    app_version: Optional[str] = None
    nozzle_type: Optional[int] = None
    
    # Operator
    flyer_name: Optional[str] = None
    team_name: Optional[str] = None
    
    # Flight settings
    radar_height: Optional[float] = None
    max_radar_height: Optional[float] = None
    work_speed: Optional[float] = None
    max_flight_speed: Optional[float] = None
    spray_width: Optional[float] = None
    
    # Work results
    new_work_area: Optional[float] = None
    spray_usage: Optional[float] = None
    min_flow_speed_per_mu: Optional[float] = None
    
    # Flags
    manual_mode: Optional[bool] = None
    use_rtk: Optional[bool] = None
    
    @property
    def start_datetime(self) -> Optional[datetime]:
        if self.start_timestamp:
            return datetime.fromtimestamp(self.start_timestamp)
        return None
    
    @property
    def end_datetime(self) -> Optional[datetime]:
        if self.end_timestamp:
            return datetime.fromtimestamp(self.end_timestamp)
        return None
    
    @property
    def duration_seconds(self) -> Optional[int]:
        if self.start_timestamp and self.end_timestamp:
            return self.end_timestamp - self.start_timestamp
        return None
    
    @property
    def duration_minutes(self) -> Optional[float]:
        if self.duration_seconds:
            return round(self.duration_seconds / 60, 1)
        return None
    
    @property
    def work_area_ha(self) -> Optional[float]:
        if self.new_work_area:
            return round(self.new_work_area / 10000, 2)
        return None
    
    @property
    def spray_usage_liters(self) -> Optional[float]:
        if self.spray_usage:
            return round(self.spray_usage / 1000, 2)
        return None
