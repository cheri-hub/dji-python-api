"""
DJI AG API - Entry Point
"""
import sys
import asyncio

# Fix para Windows: Playwright precisa de ProactorEventLoop para criar subprocessos
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
from src.infrastructure.config import get_settings


def main():
    settings = get_settings()
    
    uvicorn.run(
        "src.presentation.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
