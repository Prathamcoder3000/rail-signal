"""Configuration settings for RAIL / SIGNAL FastAPI application."""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    app_name: str = "RAIL / SIGNAL API"
    app_version: str = "0.3.0"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # PostgreSQL Database Settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "rail_signal"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    database_url: str = ""

    # CORS Settings
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # File Paths
    project_root: Path = PROJECT_ROOT
    processed_data_dir: Path = PROJECT_ROOT / "data" / "processed"
    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    quality_report_path: Path = PROJECT_ROOT / "data" / "processed" / "quality_report.json"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    # Explicitly load .env file into os.environ if present to ensure consistency
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

    settings = Settings(
        postgres_host=os.environ.get("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.environ.get("POSTGRES_PORT", 5432)),
        postgres_db=os.environ.get("POSTGRES_DB", "rail_signal"),
        postgres_user=os.environ.get("POSTGRES_USER", "postgres"),
        postgres_password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        app_port=int(os.environ.get("APP_PORT", 8000)),
    )
    return settings


settings = get_settings()
