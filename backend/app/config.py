from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ExperimentIQ"
    # Postgres in Docker/production; SQLite fallback keeps local dev zero-setup.
    database_url: str = "sqlite:///./experimentiq.db"
    api_key: str = "dev-secret-key"
    cors_origins: str = "http://localhost:3000"
    # Below this many users per arm we refuse to call a winner, whatever the p-value.
    min_users_per_variant: int = 100

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Heroku/Render/Neon hand out postgres:// URLs; SQLAlchemy + psycopg3 wants this form.
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
