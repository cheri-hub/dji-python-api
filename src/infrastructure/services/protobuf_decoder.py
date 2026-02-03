"""
Protobuf Decoder Service
"""
import struct
from collections import defaultdict
from typing import Dict, List, Tuple, Any

from ...domain.entities import FlightData, GpsPoint
from ..config import get_settings


class ProtobufDecoder:
    """Decodificador de dados protobuf binários"""
    
    def __init__(self):
        self._settings = get_settings()
    
    def _decode_varint(self, data: bytes, pos: int) -> Tuple[int, int]:
        """Decodifica um varint do protobuf"""
        result, shift = 0, 0
        while pos < len(data):
            byte = data[pos]
            result |= (byte & 0x7F) << shift
            pos += 1
            if not (byte & 0x80):
                break
            shift += 7
        return result, pos
    
    def _extract_all_values(self, data: bytes, max_depth: int = 6) -> Dict[int, Dict[str, List]]:
        """Extrai todos os valores do protobuf por profundidade"""
        all_values = defaultdict(lambda: defaultdict(list))
        
        def parse_recursive(data: bytes, depth: int = 0):
            if depth > max_depth:
                return
            pos = 0
            while pos < len(data):
                try:
                    tag, new_pos = self._decode_varint(data, pos)
                    if new_pos >= len(data):
                        break
                    pos = new_pos
                    wire_type = tag & 0x07
                    field = tag >> 3
                    
                    if wire_type == 0:  # Varint
                        val, pos = self._decode_varint(data, pos)
                        if val < 1e15:
                            all_values[depth][f'int_{field}'].append(val)
                    elif wire_type == 1:  # 64-bit (double)
                        if pos + 8 <= len(data):
                            val = struct.unpack('<d', data[pos:pos+8])[0]
                            if -1e10 < val < 1e10:
                                all_values[depth][f'dbl_{field}'].append(val)
                        pos += 8
                    elif wire_type == 2:  # Length-delimited
                        length, pos = self._decode_varint(data, pos)
                        if length and pos + length <= len(data):
                            parse_recursive(data[pos:pos+length], depth + 1)
                            pos += length
                        else:
                            break
                    elif wire_type == 5:  # 32-bit (float)
                        if pos + 4 <= len(data):
                            val = struct.unpack('<f', data[pos:pos+4])[0]
                            if -1e10 < val < 1e10:
                                all_values[depth][f'flt_{field}'].append(val)
                        pos += 4
                    else:
                        break
                except:
                    break
        
        parse_recursive(data)
        return all_values
    
    def decode(self, binary_data: bytes, record_id: str) -> FlightData:
        """Decodifica dados binários para FlightData"""
        all_values = self._extract_all_values(binary_data)
        
        # Pegar listas brutas
        raw_lats = all_values[3]['dbl_1']
        raw_lons = all_values[3]['dbl_2']
        raw_headings = all_values[3]['dbl_3']
        raw_vel_x = all_values[3]['flt_1']
        raw_vel_y = all_values[3]['flt_2']
        raw_spray = all_values[3]['flt_3']
        
        # Filtrar pares válidos de coordenadas
        points = []
        num_raw = min(len(raw_lats), len(raw_lons))
        
        lat_min = self._settings.lat_min
        lat_max = self._settings.lat_max
        lon_min = self._settings.lon_min
        lon_max = self._settings.lon_max
        
        valid_index = 0
        for i in range(num_raw):
            lat = raw_lats[i]
            lon = raw_lons[i]
            
            # Validar AMBAS coordenadas juntas
            if lat_min < lat < lat_max and lon_min < lon < lon_max:
                heading = None
                if i < len(raw_headings) and -180 <= raw_headings[i] <= 180:
                    heading = round(raw_headings[i], 2)
                
                vel_x = None
                if i < len(raw_vel_x) and -30 < raw_vel_x[i] < 30:
                    vel_x = round(raw_vel_x[i], 2)
                
                vel_y = None
                if i < len(raw_vel_y) and -30 < raw_vel_y[i] < 30:
                    vel_y = round(raw_vel_y[i], 2)
                
                spray = None
                if i < len(raw_spray) and 0 < raw_spray[i] < 50:
                    spray = round(raw_spray[i], 2)
                
                point = GpsPoint(
                    index=valid_index,
                    latitude=lat,
                    longitude=lon,
                    heading=heading,
                    velocity_x=vel_x,
                    velocity_y=vel_y,
                    spray_rate=spray,
                )
                points.append(point)
                valid_index += 1
        
        flight_data = FlightData(record_id=record_id, points=points)
        flight_data.calculate_bounds()
        flight_data.calculate_telemetry()
        
        return flight_data
