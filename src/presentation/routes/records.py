"""
Records Routes
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..dependencies import (
    get_list_records_use_case,
    get_record_use_case,
    get_download_record_use_case,
    get_flight_data_use_case,
    verify_api_key,
)
from ...application.use_cases import (
    ListRecordsUseCase,
    GetRecordUseCase,
    DownloadRecordUseCase,
    GetFlightDataUseCase,
    ListRecordsInput,
    GetRecordInput,
    DownloadRecordInput,
    GetFlightDataInput,
)

router = APIRouter(prefix="/records", dependencies=[Depends(verify_api_key)])


# ============================================================
# Response Models
# ============================================================

class RecordSummaryResponse(BaseModel):
    id: str
    takeoff_landing_time: str
    flight_duration: str
    task_mode: str
    area: str
    application_rate: str
    flight_mode: str
    pilot_name: str
    device_name: str


class RecordListResponse(BaseModel):
    items: List[RecordSummaryResponse]
    total: int
    page: int
    per_page: int


class RecordDetailResponse(BaseModel):
    id: str
    serial_number: Optional[str] = None
    hardware_id: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    duration_minutes: Optional[float] = None
    create_date: Optional[str] = None
    location: Optional[str] = None
    drone_type: Optional[str] = None
    nickname: Optional[str] = None
    flyer_name: Optional[str] = None
    team_name: Optional[str] = None
    radar_height: Optional[float] = None
    work_speed: Optional[float] = None
    spray_width: Optional[float] = None
    work_area_ha: Optional[float] = None
    spray_usage_liters: Optional[float] = None
    manual_mode: Optional[bool] = None
    use_rtk: Optional[bool] = None


class GpsPointResponse(BaseModel):
    index: int
    latitude: float
    longitude: float
    heading: Optional[float] = None
    velocity_x: Optional[float] = None
    velocity_y: Optional[float] = None
    spray_rate: Optional[float] = None
    speed_ms: Optional[float] = None


class FlightDataResponse(BaseModel):
    record_id: str
    total_points: int
    bounds: Optional[dict] = None
    telemetry: Optional[dict] = None
    points: Optional[List[GpsPointResponse]] = None


class DownloadResponse(BaseModel):
    record_id: str
    success: bool
    message: Optional[str] = None
    total_points: int = 0
    metadata: Optional[dict] = None


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=RecordListResponse)
async def list_records(
    page: int = Query(1, ge=1, description="Número da página"),
    per_page: int = Query(30, ge=1, le=100, description="Itens por página"),
    use_case: ListRecordsUseCase = Depends(get_list_records_use_case),
):
    """
    Lista todos os flight records.
    
    Retorna uma lista paginada de todos os registros de voo disponíveis.
    """
    result = await use_case.execute(ListRecordsInput(page=page, per_page=per_page))
    
    return RecordListResponse(
        items=[RecordSummaryResponse(**item.__dict__) for item in result.items],
        total=result.total,
        page=result.page,
        per_page=result.per_page,
    )


@router.get("/{record_id}", response_model=RecordDetailResponse)
async def get_record(
    record_id: str,
    use_case: GetRecordUseCase = Depends(get_record_use_case),
):
    """
    Busca detalhes de um flight record específico.
    
    Retorna metadados completos do registro de voo.
    """
    result = await use_case.execute(GetRecordInput(record_id=record_id))
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    
    return RecordDetailResponse(**result.__dict__)


@router.get("/{record_id}/flight-data", response_model=FlightDataResponse)
async def get_flight_data(
    record_id: str,
    include_points: bool = Query(True, description="Incluir pontos GPS individuais"),
    use_case: GetFlightDataUseCase = Depends(get_flight_data_use_case),
):
    """
    Busca dados de voo de um record.
    
    Retorna coordenadas GPS e telemetria do voo.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[FlightData Route] Buscando dados para record {record_id}")
        result = await use_case.execute(GetFlightDataInput(
            record_id=record_id,
            include_points=include_points,
            format="json",
        ))
        logger.info(f"[FlightData Route] Use case retornou: {result is not None}")
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Flight data for {record_id} not found")
        
        points = None
        if result.points:
            points = [GpsPointResponse(**p.__dict__) for p in result.points]
        
        return FlightDataResponse(
            record_id=result.record_id,
            total_points=result.total_points,
            bounds=result.bounds,
            telemetry=result.telemetry,
            points=points,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[FlightData Route] Erro inesperado: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{record_id}/geojson")
async def get_geojson(
    record_id: str,
    use_case: GetFlightDataUseCase = Depends(get_flight_data_use_case),
):
    """
    Retorna dados de voo em formato GeoJSON (resumido).
    
    **Aviso**: Para GeoJSON completo, use `/geojson/download` que retorna arquivo.
    Este endpoint pode travar o Swagger com muitos pontos.
    """
    result = await use_case.execute(GetFlightDataInput(
        record_id=record_id,
        include_points=True,
        format="geojson",
    ))
    
    if not result or not result.geojson:
        raise HTTPException(status_code=404, detail=f"GeoJSON for {record_id} not found")
    
    return result.geojson


@router.get("/{record_id}/geojson/download")
async def download_geojson(
    record_id: str,
    use_case: GetFlightDataUseCase = Depends(get_flight_data_use_case),
):
    """
    Baixa dados de voo como arquivo GeoJSON.
    
    Retorna arquivo `.geojson` completo com:
    - LineString da rota completa
    - Pontos individuais com telemetria (altitude, velocidade, heading, etc)
    
    **Recomendado** para GeoJSON grandes que travam o Swagger.
    """
    import json
    from fastapi.responses import Response
    
    result = await use_case.execute(GetFlightDataInput(
        record_id=record_id,
        include_points=True,
        format="geojson",
    ))
    
    if not result or not result.geojson:
        raise HTTPException(status_code=404, detail=f"GeoJSON for {record_id} not found")
    
    geojson_str = json.dumps(result.geojson, ensure_ascii=False)
    return Response(
        content=geojson_str,
        media_type="application/geo+json",
        headers={
            "Content-Disposition": f'attachment; filename="{record_id}.geojson"'
        }
    )
