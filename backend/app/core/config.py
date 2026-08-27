"""
Nova Credit AI — Core Application Settings
Environment-based configuration using pydantic-settings.
"""
import os
import json
from pathlib import Path
from typing import List
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
    SECRET_KEY: str = "nova-dev-secret-change-in-production-please-use-32-char-random-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # CORS
    ALLOWED_ORIGINS: str = "*"

    @property
    def allowed_origins_list(self) -> List[str]:
        val = self.ALLOWED_ORIGINS.strip()
        if val == "*":
            return ["*"]
        if val.startswith("[") and val.endswith("]"):
            try:
                return json.loads(val)
            except Exception:
                pass
        return [origin.strip() for origin in val.split(",") if origin.strip()]

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
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
