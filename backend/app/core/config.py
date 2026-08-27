"""
Nova Credit AI — Core Application Settings
Environment-based configuration using pydantic-settings.
Override any value via environment variables or a .env file.
"""
import os
from pathlib import Path
from functools import lru_cache
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # fallback


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Nova Credit AI"
    APP_VERSION: str = "2.2.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | testing | production

    # Database — SQLite for dev, swap via env for production Postgres
    DATABASE_URL: str = "sqlite:///./data/nova_credit.db"

    # Security
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "nova-dev-secret-change-in-production-please-use-32-char-random-key"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS — tighten in production
    ALLOWED_ORIGINS: list = ["*"]

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60   # seconds

    # ML
    PIPELINE_FILE: str = "models/nova_credit_pipeline.joblib"
    BENCHMARK_REPORT: str = "reports/model_benchmark_report.json"
    CURRENCY_SCALE: float = 100.0   # INR → DM dataset scale

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
