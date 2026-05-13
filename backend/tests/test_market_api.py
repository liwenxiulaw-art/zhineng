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


def test_refresh_quotes_falls_back_to_second_enabled_provider(client: TestClient) -> None:
    stock_response = client.post("/api/v1/stocks", json={"code": "000001", "exchange": "SZ", "name": "平安银行"})
    assert stock_response.status_code == 201
    stock_id = stock_response.json()["id"]

    assert client.post(
        "/api/v1/data-sources",
        json={"provider": "failing", "data_type": "quote", "priority": 1, "is_enabled": True},
    ).status_code == 201
    assert client.post(
        "/api/v1/data-sources",
        json={"provider": "mock", "data_type": "quote", "priority": 2, "is_enabled": True},
    ).status_code == 201

    refresh_response = client.post("/api/v1/quotes/refresh")
    assert refresh_response.status_code == 200
    refresh_body = refresh_response.json()
    assert refresh_body["provider"] == "mock"
    assert refresh_body["is_fallback"] is True
    assert refresh_body["data_status"] == "normal"
    assert refresh_body["attempted_providers"] == ["failing", "mock"]

    quote_response = client.get(f"/api/v1/stocks/{stock_id}/quote")
    assert quote_response.status_code == 200
    quote = quote_response.json()
    assert quote["source"] == "mock"
    assert quote["is_fallback"] is True

    logs_response = client.get("/api/v1/data-sources/logs")
    assert logs_response.status_code == 200
    statuses = [log["status"] for log in logs_response.json()]
    assert "failed" in statuses
    assert "fallback" in statuses


def test_quote_health_detects_invalid_and_stale_payloads(client: TestClient) -> None:
    assert client.post("/api/v1/stocks", json={"code": "600519", "exchange": "SH", "name": "贵州茅台"}).status_code == 201

    invalid_response = client.post("/api/v1/quotes/refresh?provider=missing_price")
    assert invalid_response.status_code == 200
    invalid_body = invalid_response.json()
    assert invalid_body["data_status"] == "abnormal"
    assert invalid_body["refreshed_count"] == 1

    latest_response = client.get("/api/v1/quotes/latest")
    assert latest_response.status_code == 200
    latest_quote = latest_response.json()[0]
    assert latest_quote["data_status"] == "abnormal"
    assert latest_quote["abnormal_reason"] == "当前价为空"

    stale_response = client.post("/api/v1/quotes/refresh?provider=stale")
    assert stale_response.status_code == 200
    stale_body = stale_response.json()
    assert stale_body["data_status"] == "stale"

    health_response = client.get("/api/v1/data-sources/health")
    assert health_response.status_code == 200
    issue_types = [record["issue_type"] for record in health_response.json()]
    assert "price_missing" in issue_types
    assert "timestamp_stale" in issue_types


def test_unknown_quote_provider_returns_400(client: TestClient) -> None:
    assert client.post("/api/v1/stocks", json={"code": "300750", "exchange": "SZ", "name": "宁德时代"}).status_code == 201

    response = client.post("/api/v1/quotes/refresh?provider=unknown")
    assert response.status_code == 400
    assert "未知行情数据源" in response.json()["detail"]
