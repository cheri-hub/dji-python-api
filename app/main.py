from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime

from app.config import settings
from app.routes import router
from app.services.djiag_service import dji_service
from app.models import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                      DJI AG API                            ║
╠════════════════════════════════════════════════════════════╣
║  🚀 Server running on: http://localhost:{settings.port:<17}║
║  📁 Downloads path: {str(settings.get_download_path())[:35]:<37}║
║  🌐 Headless mode: {str(settings.headless):<38}║
╚════════════════════════════════════════════════════════════╝
    """)
    yield
    # Cleanup
    print("\n🛑 Shutting down...")
    await dji_service.close()


app = FastAPI(
    title="DJI AG API",
    description="API para automação de download de records do DJI AG",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas
app.include_router(router)


@app.get("/", tags=["Root"])
async def root():
    """Retorna informações da API"""
    return {
        "name": "DJI AG API",
        "version": "1.0.0",
        "description": "API para automação de download de records do DJI AG",
        "endpoints": {
            "GET /health": "Health check",
            "GET /api/status": "Session status",
            "POST /api/auth/login": "Login with credentials",
            "POST /api/auth/logout": "Logout and close session",
            "GET /api/records": "List all records",
            "POST /api/records/{id}/download": "Download specific record",
            "POST /api/records/download-all": "Download all records",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(),
        session=dji_service.get_session_status(),
    )
