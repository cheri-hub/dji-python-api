"""
Domain Entity: Flight Data (GPS + Telemetry)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .record import Record


@dataclass
class GpsPoint:
    """Um ponto GPS com telemetria"""
    index: int
    latitude: float
    longitude: float
    heading: Optional[float] = None
    velocity_x: Optional[float] = None
    velocity_y: Optional[float] = None
    spray_rate: Optional[float] = None
    
    @property
    def speed_ms(self) -> Optional[float]:
        if self.velocity_x is not None and self.velocity_y is not None:
            return round((self.velocity_x**2 + self.velocity_y**2)**0.5, 2)
        return None
    
    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "heading": self.heading,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "spray_rate": self.spray_rate,
            "speed_ms": self.speed_ms,
        }


@dataclass
class Telemetry:
    """Estatísticas de telemetria agregadas"""
    heading_avg: Optional[float] = None
    heading_min: Optional[float] = None
    heading_max: Optional[float] = None
    speed_avg_ms: Optional[float] = None
    speed_max_ms: Optional[float] = None
    spray_rate_avg: Optional[float] = None
    spray_rate_min: Optional[float] = None
    spray_rate_max: Optional[float] = None


@dataclass
class GpsBounds:
    """Limites geográficos"""
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    
    @property
    def center_lat(self) -> float:
        return (self.lat_min + self.lat_max) / 2
    
    @property
    def center_lon(self) -> float:
        return (self.lon_min + self.lon_max) / 2


@dataclass
class FlightData:
    """Dados de voo completos"""
    record_id: str
    points: List[GpsPoint] = field(default_factory=list)
    telemetry: Optional[Telemetry] = None
    bounds: Optional[GpsBounds] = None
    
    @property
    def total_points(self) -> int:
        return len(self.points)
    
    def calculate_bounds(self) -> Optional[GpsBounds]:
        if not self.points:
            return None
        
        lats = [p.latitude for p in self.points]
        lons = [p.longitude for p in self.points]
        
        self.bounds = GpsBounds(
            lat_min=min(lats),
            lat_max=max(lats),
            lon_min=min(lons),
            lon_max=max(lons),
        )
        return self.bounds
    
    def calculate_telemetry(self) -> Telemetry:
        headings = [p.heading for p in self.points if p.heading is not None]
        speeds = [p.speed_ms for p in self.points if p.speed_ms is not None]
        sprays = [p.spray_rate for p in self.points if p.spray_rate is not None]
        
        self.telemetry = Telemetry(
            heading_avg=round(sum(headings) / len(headings), 2) if headings else None,
            heading_min=round(min(headings), 2) if headings else None,
            heading_max=round(max(headings), 2) if headings else None,
            speed_avg_ms=round(sum(speeds) / len(speeds), 2) if speeds else None,
            speed_max_ms=round(max(speeds), 2) if speeds else None,
            spray_rate_avg=round(sum(sprays) / len(sprays), 2) if sprays else None,
            spray_rate_min=round(min(sprays), 2) if sprays else None,
            spray_rate_max=round(max(sprays), 2) if sprays else None,
        )
        return self.telemetry
    
    def to_geojson(self, record: 'Record' = None) -> dict:
        """Converte para GeoJSON"""
        # LineString da rota
        route_feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[p.longitude, p.latitude] for p in self.points]
            },
            "properties": {
                "type": "flight_path",
                "total_points": self.total_points
            }
        }
        
        # Pontos individuais
        point_features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [p.longitude, p.latitude]
                },
                "properties": p.to_dict()
            }
            for p in self.points
        ]
        
        # Properties do FeatureCollection
        properties = {
            "record_id": self.record_id,
            "total_points": self.total_points,
        }
        
        if self.bounds:
            properties["gps"] = {
                "lat_min": self.bounds.lat_min,
                "lat_max": self.bounds.lat_max,
                "lon_min": self.bounds.lon_min,
                "lon_max": self.bounds.lon_max,
                "center_lat": self.bounds.center_lat,
                "center_lon": self.bounds.center_lon,
            }
        
        if self.telemetry:
            properties["telemetry"] = {
                "heading_avg": self.telemetry.heading_avg,
                "heading_min": self.telemetry.heading_min,
                "heading_max": self.telemetry.heading_max,
                "speed_avg_ms": self.telemetry.speed_avg_ms,
                "speed_max_ms": self.telemetry.speed_max_ms,
                "spray_rate_avg": self.telemetry.spray_rate_avg,
            }
        
        # Adicionar metadados do record se disponível
        if record:
            properties.update({
                "flight_record_number": record.id,
                "serial_number": record.serial_number,
                "date": record.create_date,
                "start_datetime": record.start_datetime.isoformat() if record.start_datetime else None,
                "end_datetime": record.end_datetime.isoformat() if record.end_datetime else None,
                "duration_minutes": record.duration_minutes,
                "location": record.location,
                "drone_type": record.drone_type,
                "nickname": record.nickname,
                "pilot_name": record.flyer_name,
                "flight_height_m": record.radar_height,
                "work_area_ha": record.work_area_ha,
                "spray_usage_L": record.spray_usage_liters,
            })
        
        return {
            "type": "FeatureCollection",
            "name": f"DJI AG Flight {self.record_id}",
            "properties": properties,
            "features": [route_feature] + point_features
        }
