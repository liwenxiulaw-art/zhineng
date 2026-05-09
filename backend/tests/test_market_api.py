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
        Base.metadata.drop_all(bind=engine)


def test_refresh_quotes_writes_quotes_health_and_logs(client: TestClient) -> None:
    stock_response = client.post(
        "/api/v1/stocks",
        json={"code": "000001", "exchange": "SZ", "name": "平安银行", "industry": "银行"},
    )
    assert stock_response.status_code == 201
    stock_id = stock_response.json()["id"]

    refresh_response = client.post("/api/v1/quotes/refresh")
    assert refresh_response.status_code == 200
    refresh_body = refresh_response.json()
    assert refresh_body["provider"] == "mock"
    assert refresh_body["data_status"] == "normal"
    assert refresh_body["refreshed_count"] == 1
    assert refresh_body["failed_symbols"] == []

    latest_response = client.get("/api/v1/quotes/latest")
    assert latest_response.status_code == 200
    latest_quotes = latest_response.json()
    assert len(latest_quotes) == 1
    assert latest_quotes[0]["stock_id"] == stock_id
    assert latest_quotes[0]["source"] == "mock"
    assert latest_quotes[0]["data_status"] == "normal"
    assert latest_quotes[0]["price"] > 0

    single_response = client.get(f"/api/v1/stocks/{stock_id}/quote")
    assert single_response.status_code == 200
    assert single_response.json()["id"] == latest_quotes[0]["id"]

    health_response = client.get("/api/v1/data-sources/health")
    assert health_response.status_code == 200
    health_records = health_response.json()
    assert len(health_records) == 1
    assert health_records[0]["status"] == "normal"

    logs_response = client.get("/api/v1/data-sources/logs")
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["status"] == "success"
    assert logs[0]["records_count"] == 1


def test_refresh_quotes_handles_empty_pool_and_provider_failure(client: TestClient) -> None:
    empty_response = client.post("/api/v1/quotes/refresh")
    assert empty_response.status_code == 200
    assert empty_response.json()["data_status"] == "missing"
    assert empty_response.json()["refreshed_count"] == 0

    stock_response = client.post("/api/v1/stocks", json={"code": "600519", "exchange": "SH", "name": "贵州茅台"})
    assert stock_response.status_code == 201

    failure_response = client.post("/api/v1/quotes/refresh?provider=failing")
    assert failure_response.status_code == 200
    failure_body = failure_response.json()
    assert failure_body["data_status"] == "abnormal"
    assert failure_body["refreshed_count"] == 0
    assert failure_body["failed_symbols"] == ["600519.SH"]

    logs_response = client.get("/api/v1/data-sources/logs")
    assert logs_response.status_code == 200
    statuses = [log["status"] for log in logs_response.json()]
    assert "failed" in statuses
    assert "skipped" in statuses


def test_can_create_data_source_config(client: TestClient) -> None:
    response = client.post(
        "/api/v1/data-sources",
        json={
            "provider": "mock",
            "data_type": "quote",
            "priority": 10,
            "is_enabled": True,
            "rate_limit_per_minute": 120,
            "timeout_seconds": 5,
            "max_retry": 1,
        },
    )
    assert response.status_code == 201
    assert response.json()["priority"] == 10

    list_response = client.get("/api/v1/data-sources?data_type=quote")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
