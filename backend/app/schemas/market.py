from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DataType = Literal["quote", "kline", "financial", "news"]
FetchStatus = Literal["success", "failed", "fallback", "skipped"]
HealthStatus = Literal["normal", "healthy", "stale", "abnormal", "missing", "partial"]


class DataSourceConfigBase(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    data_type: DataType = "quote"
    priority: int = 100
    is_enabled: bool = True
    rate_limit_per_minute: int | None = Field(default=None, ge=1)
    timeout_seconds: int = Field(default=10, ge=1)
    max_retry: int = Field(default=1, ge=0)
    config_json: str | None = None


class DataSourceConfigCreate(DataSourceConfigBase):
    pass


class DataSourceConfigRead(DataSourceConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class DataFetchLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    data_type: str
    endpoint: str
    request_key: str | None
    status: str
    error_message: str | None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    records_count: int
    used_fallback: bool
    created_at: datetime


class DataHealthCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data_type: str
    stock_id: int | None
    provider: str
    check_time: datetime
    status: str
    issue_type: str | None
    issue_detail: str | None
    last_valid_data_at: datetime | None
    created_at: datetime


class QuotePayload(BaseModel):
    symbol: str
    trade_date: date | None = None
    quote_time: datetime | None = None
    price: float | None = None
    change_amount: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    pe: float | None = None
    total_market_cap: float | None = None
    float_market_cap: float | None = None
    raw_data: str | None = None


class MarketQuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    trade_date: date | None
    quote_time: datetime | None
    price: float | None
    change_amount: float | None
    change_pct: float | None
    volume: float | None
    amount: float | None
    turnover_rate: float | None
    volume_ratio: float | None
    pe: float | None
    total_market_cap: float | None
    float_market_cap: float | None
    source: str
    source_priority: int
    is_fallback: bool
    data_status: str
    abnormal_reason: str | None
    raw_data: str | None
    created_at: datetime


class QuoteRefreshResult(BaseModel):
    provider: str
    is_fallback: bool
    data_status: str
    refreshed_count: int
    failed_symbols: list[str] = Field(default_factory=list)
    fetch_log_id: int | None = None
    attempted_providers: list[str] = Field(default_factory=list)


class QuoteHealthIssue(BaseModel):
    status: str
    issue_type: str | None = None
    issue_detail: str | None = None
