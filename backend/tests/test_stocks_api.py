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


def test_stock_tag_research_card_and_discipline_plan_crud(client: TestClient) -> None:
    tag_response = client.post("/api/v1/tags", json={"name": "AI", "category": "theme", "color": "#1677ff"})
    assert tag_response.status_code == 201
    tag_id = tag_response.json()["id"]

    stock_response = client.post(
        "/api/v1/stocks",
        json={
            "code": "600519",
            "exchange": "SH",
            "name": "贵州茅台",
            "industry": "白酒",
            "concepts": "高端消费",
            "holding_status": "watching",
            "is_focus": True,
            "tag_ids": [tag_id],
        },
    )
    assert stock_response.status_code == 201
    stock = stock_response.json()
    assert stock["symbol"] == "600519.SH"
    assert stock["tags"][0]["name"] == "AI"
    stock_id = stock["id"]

    card_response = client.put(
        f"/api/v1/stocks/{stock_id}/research-card",
        json={
            "investment_thesis": "长期品牌壁垒观察。",
            "core_business": "高端白酒。",
            "risk_points": "消费需求波动。",
            "has_earnings_support": True,
            "has_policy_driver": False,
            "has_theme_speculation": False,
        },
    )
    assert card_response.status_code == 200
    assert card_response.json()["investment_thesis"] == "长期品牌壁垒观察。"

    plan_response = client.put(
        f"/api/v1/stocks/{stock_id}/discipline-plan",
        json={
            "target_buy_price": 1500,
            "target_sell_price": 1900,
            "stop_loss_price": 1350,
            "position_plan": "分批观察。",
            "max_drawdown_pct": 10,
            "allow_chasing_high": False,
            "plan_reason": "用于执行交易纪律。",
            "is_active": True,
        },
    )
    assert plan_response.status_code == 200
    assert plan_response.json()["stop_loss_price"] == 1350

    list_response = client.get(f"/api/v1/stocks?tag_id={tag_id}")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    archive_response = client.delete(f"/api/v1/stocks/{stock_id}")
    assert archive_response.status_code == 200
    assert archive_response.json()["is_active"] is False

    active_list_response = client.get("/api/v1/stocks")
    assert active_list_response.status_code == 200
    assert active_list_response.json() == []


def test_duplicate_stock_is_rejected(client: TestClient) -> None:
    payload = {"code": "000001", "exchange": "SZ", "name": "平安银行"}
    assert client.post("/api/v1/stocks", json=payload).status_code == 201
    response = client.post("/api/v1/stocks", json=payload)
    assert response.status_code == 409
