"""
Health Check Routes
"""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Verifica a saúde da API"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )
