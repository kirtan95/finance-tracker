"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os


def _get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Settings:
    # SQLite for local dev; switch to PostgreSQL with e.g.
    # postgresql+psycopg2://finance:finance@db:5432/finance
    DATABASE_URL: str = _get_env("DATABASE_URL", "sqlite:///./finance.db")
    SECRET_KEY: str = _get_env("SECRET_KEY", "dev-secret-key-change-me")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        _get_env("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in _get_env("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    ALGORITHM: str = "HS256"


settings = Settings()
