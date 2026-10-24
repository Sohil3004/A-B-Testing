from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_db_url() -> str:
    if os.getenv("VERCEL"):
        tmp_db = (Path(tempfile.gettempdir()) / "experimentiq.db").as_posix()
        return f"sqlite:///{tmp_db}"
    return "sqlite:///./experimentiq.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ExperimentIQ"
    # Postgres in Docker/production; SQLite fallback (/tmp on Vercel serverless) keeps setup zero-config.
    database_url: str = _default_db_url()
    api_key: str = "dev-secret-key"
    cors_origins: str = "*" if os.getenv("VERCEL") else "http://localhost:3000"
    # Below this many users per arm we refuse to call a winner, whatever the p-value.
    min_users_per_variant: int = 100

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Heroku/Render/Neon/Supabase hand out postgres:// URLs; SQLAlchemy + psycopg3 wants this form.
        if v.startswith("postgres://"):
            v = "postgresql+psycopg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
