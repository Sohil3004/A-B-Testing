from __future__ import annotations

import os

os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_db
from app.main import app

API_KEY = "test-key"


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    s = session_factory()
    yield s
    s.close()


@pytest.fixture()
def client(session_factory):
    def _get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    get_settings.cache_clear()
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app, headers={"X-API-Key": API_KEY}) as c:
        yield c
    app.dependency_overrides.clear()
