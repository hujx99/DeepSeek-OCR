from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DocFlow OCR"
    database_url: str = "sqlite:///./docflow.db"
    redis_url: str = "redis://localhost:6379/0"
    local_storage_root: Path = Path("./storage")
    ocr_provider: str = "mock"
    deepseek_ocr2_endpoint: str | None = None
    deepseek_ocr2_api_key: str | None = None
    mock_auth_email: str = "demo@docflow.local"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_bytes: int = 50 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def upload_dir(self) -> Path:
        return self.local_storage_root / "uploads"

    @property
    def export_dir(self) -> Path:
        return self.local_storage_root / "exports"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    return settings
