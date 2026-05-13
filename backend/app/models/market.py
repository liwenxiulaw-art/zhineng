from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DataSourceConfig(Base):
    __tablename__ = "data_source_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_retry: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DataFetchLog(Base):
    __tablename__ = "data_fetch_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    request_key: Mapped[str | None] = mapped_column(String(256), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class DataHealthCheck(Base):
    __tablename__ = "data_health_checks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    data_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    check_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    issue_type: Mapped[str | None] = mapped_column(String(64), index=True)
    issue_detail: Mapped[str | None] = mapped_column(Text)
    last_valid_data_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    stock: Mapped["Stock | None"] = relationship("Stock")


class MarketQuote(Base):
    __tablename__ = "market_quotes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True, nullable=False)
    trade_date: Mapped[date | None] = mapped_column(Date, index=True)
    quote_time: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    price: Mapped[float | None] = mapped_column(Float)
    change_amount: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    turnover_rate: Mapped[float | None] = mapped_column(Float)
    volume_ratio: Mapped[float | None] = mapped_column(Float)
    pe: Mapped[float | None] = mapped_column(Float)
    total_market_cap: Mapped[float | None] = mapped_column(Float)
    float_market_cap: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    abnormal_reason: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    stock: Mapped["Stock"] = relationship("Stock")
