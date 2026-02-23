from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    smb_host: str = "smb"
    smb_share: str = "embroidery"
    smb_username: str = "embroidery"
    smb_password: str = "embroidery123"
    smb_port: int = 445
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    openai_api_key: str | None = None
    ollama_base_url: str | None = "http://ollama:11434"
    tag_cron_hour: int = 3
    tag_cron_minute: int = 0

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
