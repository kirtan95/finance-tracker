"""Finance Tracker backend — FastAPI app factory and route wiring."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from . import models  # noqa: F401 - ensure models are registered on Base
from .routers import (
    accounts,
    auth_router,
    categories,
    import_csv,
    summary,
    transactions,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Finance Tracker API",
        description="Personal finance tracking: accounts, transactions, budgets, CSV import.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router.router, prefix="/api")
    app.include_router(accounts.router, prefix="/api")
    app.include_router(transactions.router, prefix="/api")
    app.include_router(categories.router, prefix="/api")
    app.include_router(summary.router, prefix="/api")
    app.include_router(import_csv.router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
