"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""
    whisper_model: str = "base"
    test_user_id: str = ""
    frontend_url: str = "https://meetmind-nine.vercel.app"
    mock_mode: bool = False
    cron_secret: str = ""

    # Gemini model for MOM / summary generation
    gemini_model: str = "gemini-1.5-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()
