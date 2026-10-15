# config.py - RevIA API
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    gemini_api_key: str = ""
    api_token: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"  # vide : pas de modèle de secours
    gemini_timeout_s: int = 120   # par tentative
    gemini_attempts: int = 2      # tentatives au total, nouvel essai compris
    max_pdf_mb: int = 20
    rate_limit_per_minute: int = 10
    cache_dir: str = ".cache"
    log_level: str = "INFO"

settings = Settings()