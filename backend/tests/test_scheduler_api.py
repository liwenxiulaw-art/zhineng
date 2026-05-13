import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.tasks.scheduler import stop_scheduler


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(
            f"sqlite:///{Path(tmpdir) / 'test.db'}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)

        def override_get_db() -> Generator[Session, None, None]:
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()
        stop_scheduler()
        Base.metadata.drop_all(bind=engine)


def test_scheduler_status_and_manual_quote_job(client: TestClient) -> None:
    status_response = client.get("/api/v1/system/scheduler")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["quote_job_registered"] is True
    assert status["quote_refresh_interval_seconds"] == 15
    assert status["skip_non_trading"] is True

    stock_response = client.post("/api/v1/stocks", json={"code": "000001", "exchange": "SZ", "name": "平安银行"})
    assert stock_response.status_code == 201

    run_response = client.post("/api/v1/system/scheduler/quote-refresh/run?force=true")
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["job_result"]["last_status"] == "success"
    assert body["job_result"]["last_result"]["refreshed_count"] == 1

    latest_response = client.get("/api/v1/quotes/latest")
    assert latest_response.status_code == 200
    assert len(latest_response.json()) == 1


def test_scheduler_start_and_stop(client: TestClient) -> None:
    start_response = client.post("/api/v1/system/scheduler/start")
    assert start_response.status_code == 200
    assert start_response.json()["running"] is True

    stop_response = client.post("/api/v1/system/scheduler/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False
