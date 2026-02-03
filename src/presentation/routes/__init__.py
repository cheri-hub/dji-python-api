from .records import router as records_router
from .health import router as health_router
from .auth import router as auth_router

__all__ = ['records_router', 'health_router', 'auth_router']
