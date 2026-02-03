"""
Configuration settings
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# Diretório base do projeto
BASE_DIR = Path(__file__).parent.parent.parent.parent


@dataclass
class Settings:
    """Application settings"""
    
    # DJI Credentials
    DJI_USERNAME: str = os.getenv("DJI_USERNAME", "")
    dji_password: str = os.getenv("DJI_PASSWORD", "")
    
    # Browser settings
    browser_headless: bool = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    browser_profile_dir: str = os.getenv("BROWSER_PROFILE_DIR", str(BASE_DIR / "browser_profile"))
    
    # API settings
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    api_key: str = os.getenv("API_KEY", "")
    
    # Downloads
    downloads_dir: str = os.getenv("DOWNLOADS_DIR", str(BASE_DIR / "downloads"))
    
    # Coordinate filters (Brazil)
    lat_min: float = float(os.getenv("LAT_MIN", "-35"))
    lat_max: float = float(os.getenv("LAT_MAX", "-5"))
    lon_min: float = float(os.getenv("LON_MIN", "-75"))
    lon_max: float = float(os.getenv("LON_MAX", "-35"))
    
    @classmethod
    def from_env(cls) -> "Settings":
        return cls()


# Singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
