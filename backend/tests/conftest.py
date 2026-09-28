"""Shared pytest fixtures: temp SQLite DB + TestClient with overridden get_db."""
from __future__ import annotations

import os

# Must be set before `app` is imported: the app module binds its default
# engine at import time, and the lifespan creates tables on it. Point it at a
# throwaway file so test runs never touch a developer's real ./finance.db.
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/finance_test_default.db")

import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import create_app


@pytest.fixture()
def db_session():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(
        f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.unlink(tmp.name)


@pytest.fixture()
def client(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    """Register a user, log in, return Authorization headers."""
    email = "test@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "name": "Test User", "password": "password123"},
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": "password123"}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def account_id(client, auth_headers):
    resp = client.post(
        "/api/accounts",
        json={"name": "Checking", "account_type": "checking", "starting_balance": 1000.0},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture()
def category_id(client, auth_headers):
    resp = client.get("/api/categories", headers=auth_headers)
    assert resp.status_code == 200
    cats = {c["name"]: c["id"] for c in resp.json()}
    assert "Groceries" in cats  # seeded at registration
    return cats["Groceries"]
