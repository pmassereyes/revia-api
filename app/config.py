# config.py - RevIA API
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    gemini_api_key: str = ""
    api_token: str = ""

settings = Settings()