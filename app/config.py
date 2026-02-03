import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()


class Settings:
    """Configurações da aplicação"""
    
    def __init__(self):
        # DJI Credentials
        self.dji_username: str = os.getenv("DJI_USERNAME", "")
        self.dji_password: str = os.getenv("DJI_PASSWORD", "")
        
        # URLs
        self.dji_login_url: str = "https://www.djiag.com/login"
        self.dji_records_url: str = "https://www.djiag.com/records"
        self.dji_base_url: str = "https://www.djiag.com"
        
        # API Configuration
        self.port: int = int(os.getenv("PORT", "8000"))
        
        # Download Configuration
        self.download_path: str = os.getenv("DOWNLOAD_PATH", "./downloads")
        
        # Browser Configuration
        self.headless: bool = os.getenv("HEADLESS", "true").lower() == "true"
    
    def get_download_path(self) -> Path:
        """Retorna o caminho absoluto para downloads"""
        path = Path(self.download_path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
