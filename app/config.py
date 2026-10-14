# config.py - RevIA API
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    gemini_api_key: str = ""
    api_token: str = ""
    gemini_model: str = "gemini-3.8-flash"
    max_pdf_mb: int = 20
    rate_limit_per_minute: int = 10
    cache_dir: str = ".cache"
    log_level: str = "INFO"

settings = Settings()