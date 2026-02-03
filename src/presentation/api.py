"""
FastAPI Application
"""
import sys
import asyncio

# Fix para Windows: Playwright precisa de ProactorEventLoop para criar subprocessos
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import records_router, health_router, auth_router
from ..infrastructure.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    settings = get_settings()
    print(f"🚀 Starting DJI AG API on {settings.api_host}:{settings.api_port}")
    print("ℹ️  Browser will be initialized on first request (lazy loading)")
    
    yield
    
    # Cleanup - browser fecha automaticamente quando o processo termina
    print("👋 Shutting down API")


def create_app() -> FastAPI:
    """Factory para criar a aplicação FastAPI"""
    settings = get_settings()
    
    app = FastAPI(
        title="DJI AG API",
        description="API para automação do DJI AG SmartFarm - Download e processamento de registros de voo de drones agrícolas",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Rotas
    app.include_router(health_router, prefix=settings.api_prefix, tags=["Health"])
    app.include_router(auth_router, prefix=settings.api_prefix, tags=["Auth"])
    app.include_router(records_router, prefix=settings.api_prefix, tags=["Records"])
    
    return app


app = create_app()
