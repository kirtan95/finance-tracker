"""Small shared helpers."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session


def month_expr_for(db: Session, column):
    """Render a date column as 'YYYY-MM'.

    Dialect-aware so the same code runs on SQLite (dev) and
    PostgreSQL (docker compose / production).
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return func.to_char(column, "YYYY-MM")
    return func.strftime("%Y-%m", column)
