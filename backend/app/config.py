from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./setu.db"
    cors_origins: list[str] = ["http://localhost:3000"]
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = ""
    jwt_secret: str = "local-demo-only-change-this-secret"
    speech_provider: str = "none"
    sarvam_api_key: str = ""
    channel_adapter: str = "simulator"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    demo_mode: bool = True
    clinic_name: str = "Demo Clinic"
    default_tz: str = "Asia/Kolkata"
    llm_timeout_s: float = 8.0
    speech_timeout_s: float = 6.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
