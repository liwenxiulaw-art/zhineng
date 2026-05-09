from datetime import UTC, datetime
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import DataFetchLog, DataHealthCheck, DataSourceConfig, MarketQuote, Stock
from app.schemas import DataSourceConfigCreate, QuotePayload
from app.schemas.market import QuoteHealthIssue, QuoteRefreshResult


class QuoteProvider:
    name = "base"
    priority = 100

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        raise NotImplementedError


class MockQuoteProvider(QuoteProvider):
    """Deterministic local quote provider for tests and offline development."""

    name = "mock"
    priority = 100

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        now = datetime.now(UTC).replace(tzinfo=None)
        payloads: list[QuotePayload] = []
        for index, stock in enumerate(stocks, start=1):
            base_price = 10 + index
            payloads.append(
                QuotePayload(
                    symbol=stock.symbol,
                    trade_date=now.date(),
                    quote_time=now,
                    price=round(base_price, 2),
                    change_amount=round(index * 0.03, 2),
                    change_pct=round(index * 0.25, 2),
                    volume=float(index * 10000),
                    amount=float(index * 1000000),
                    turnover_rate=round(index * 0.4, 2),
                    volume_ratio=round(1 + index * 0.05, 2),
                    pe=round(15 + index * 0.2, 2),
                    total_market_cap=float(index * 10_000_000_000),
                    float_market_cap=float(index * 8_000_000_000),
                    raw_data=f'{{"provider":"mock","symbol":"{stock.symbol}"}}',
                )
            )
        return payloads


class FailingQuoteProvider(QuoteProvider):
    name = "failing"
    priority = 100

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        raise RuntimeError("模拟数据源失败")


PROVIDERS: dict[str, type[QuoteProvider]] = {
    MockQuoteProvider.name: MockQuoteProvider,
    FailingQuoteProvider.name: FailingQuoteProvider,
}


def get_provider(name: str) -> QuoteProvider:
    provider_class = PROVIDERS.get(name)
    if provider_class is None:
        raise ValueError(f"未知行情数据源：{name}")
    return provider_class()


def list_data_source_configs(db: Session, *, data_type: str | None = None) -> list[DataSourceConfig]:
    stmt = select(DataSourceConfig).order_by(DataSourceConfig.data_type.asc(), DataSourceConfig.priority.asc())
    if data_type is not None:
        stmt = stmt.where(DataSourceConfig.data_type == data_type)
    return list(db.scalars(stmt))


def create_data_source_config(db: Session, payload: DataSourceConfigCreate) -> DataSourceConfig:
    config = DataSourceConfig(**payload.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def ensure_default_quote_source(db: Session) -> DataSourceConfig:
    config = db.scalar(
        select(DataSourceConfig)
        .where(DataSourceConfig.data_type == "quote", DataSourceConfig.is_enabled.is_(True))
        .order_by(DataSourceConfig.priority.asc())
        .limit(1)
    )
    if config is not None:
        return config
    config = DataSourceConfig(provider="mock", data_type="quote", priority=100, is_enabled=True)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def _quote_health(payload: QuotePayload) -> QuoteHealthIssue:
    if payload.price is None:
        return QuoteHealthIssue(status="abnormal", issue_type="price_missing", issue_detail="当前价为空")
    if payload.price <= 0:
        return QuoteHealthIssue(status="abnormal", issue_type="price_invalid", issue_detail="当前价小于或等于 0")
    if payload.quote_time is None:
        return QuoteHealthIssue(status="partial", issue_type="timestamp_missing", issue_detail="行情时间为空")
    if payload.change_pct is None:
        return QuoteHealthIssue(status="partial", issue_type="field_missing", issue_detail="涨跌幅为空")
    return QuoteHealthIssue(status="normal")


def _write_fetch_log(
    db: Session,
    *,
    provider: str,
    endpoint: str,
    request_key: str | None,
    status: str,
    started_at: datetime,
    records_count: int,
    used_fallback: bool = False,
    error_message: str | None = None,
) -> DataFetchLog:
    finished_at = datetime.now(UTC).replace(tzinfo=None)
    log = DataFetchLog(
        provider=provider,
        data_type="quote",
        endpoint=endpoint,
        request_key=request_key,
        status=status,
        error_message=error_message,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        records_count=records_count,
        used_fallback=used_fallback,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def refresh_quotes(db: Session, *, provider_name: str | None = None) -> QuoteRefreshResult:
    stocks = list(db.scalars(select(Stock).where(Stock.is_active.is_(True)).order_by(Stock.id.asc())))
    if not stocks:
        log = _write_fetch_log(
            db,
            provider=provider_name or "none",
            endpoint="fetch_quotes",
            request_key=None,
            status="skipped",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            records_count=0,
        )
        return QuoteRefreshResult(provider=log.provider, is_fallback=False, data_status="missing", refreshed_count=0, fetch_log_id=log.id)

    config = ensure_default_quote_source(db)
    selected_provider = provider_name or config.provider
    provider = get_provider(selected_provider)
    request_key = ",".join(stock.symbol for stock in stocks)
    started_at = datetime.now(UTC).replace(tzinfo=None)
    try:
        payloads = provider.fetch_quotes(stocks)
    except Exception as exc:
        log = _write_fetch_log(
            db,
            provider=selected_provider,
            endpoint="fetch_quotes",
            request_key=request_key,
            status="failed",
            started_at=started_at,
            records_count=0,
            error_message=str(exc),
        )
        return QuoteRefreshResult(
            provider=selected_provider,
            is_fallback=False,
            data_status="abnormal",
            refreshed_count=0,
            failed_symbols=[stock.symbol for stock in stocks],
            fetch_log_id=log.id,
        )

    payload_by_symbol = {payload.symbol: payload for payload in payloads}
    refreshed_count = 0
    failed_symbols: list[str] = []
    statuses: list[str] = []

    for stock in stocks:
        payload = payload_by_symbol.get(stock.symbol)
        if payload is None:
            failed_symbols.append(stock.symbol)
            health = DataHealthCheck(
                data_type="quote",
                stock_id=stock.id,
                provider=provider.name,
                status="missing",
                issue_type="quote_missing",
                issue_detail="数据源未返回该股票行情",
            )
            db.add(health)
            statuses.append("missing")
            continue

        issue = _quote_health(payload)
        quote = MarketQuote(
            stock_id=stock.id,
            trade_date=payload.trade_date,
            quote_time=payload.quote_time,
            price=payload.price,
            change_amount=payload.change_amount,
            change_pct=payload.change_pct,
            volume=payload.volume,
            amount=payload.amount,
            turnover_rate=payload.turnover_rate,
            volume_ratio=payload.volume_ratio,
            pe=payload.pe,
            total_market_cap=payload.total_market_cap,
            float_market_cap=payload.float_market_cap,
            source=provider.name,
            source_priority=config.priority,
            is_fallback=False,
            data_status=issue.status,
            abnormal_reason=issue.issue_detail,
            raw_data=payload.raw_data,
        )
        db.add(quote)
        db.flush()

        db.add(
            DataHealthCheck(
                data_type="quote",
                stock_id=stock.id,
                provider=provider.name,
                status=issue.status,
                issue_type=issue.issue_type,
                issue_detail=issue.issue_detail,
                last_valid_data_at=payload.quote_time if issue.status == "normal" else None,
            )
        )
        refreshed_count += 1
        statuses.append(issue.status)

    db.commit()
    log = _write_fetch_log(
        db,
        provider=provider.name,
        endpoint="fetch_quotes",
        request_key=request_key,
        status="success" if not failed_symbols else "fallback",
        started_at=started_at,
        records_count=refreshed_count,
        used_fallback=False,
    )

    overall_status = "normal" if statuses and all(status == "normal" for status in statuses) else "partial"
    if refreshed_count == 0:
        overall_status = "missing"
    return QuoteRefreshResult(
        provider=provider.name,
        is_fallback=False,
        data_status=overall_status,
        refreshed_count=refreshed_count,
        failed_symbols=failed_symbols,
        fetch_log_id=log.id,
    )


def list_latest_quotes(db: Session) -> list[MarketQuote]:
    latest_ids = (
        select(func.max(MarketQuote.id).label("latest_id"))
        .join(Stock, Stock.id == MarketQuote.stock_id)
        .where(Stock.is_active.is_(True))
        .group_by(MarketQuote.stock_id)
        .subquery()
    )
    stmt = select(MarketQuote).where(MarketQuote.id.in_(select(latest_ids.c.latest_id))).order_by(MarketQuote.stock_id.asc())
    return list(db.scalars(stmt))


def get_latest_quote(db: Session, stock_id: int) -> MarketQuote | None:
    return db.scalar(
        select(MarketQuote).where(MarketQuote.stock_id == stock_id).order_by(desc(MarketQuote.id)).limit(1)
    )


def list_fetch_logs(db: Session, *, limit: int = 50) -> list[DataFetchLog]:
    return list(db.scalars(select(DataFetchLog).order_by(desc(DataFetchLog.id)).limit(limit)))


def list_health_checks(db: Session, *, limit: int = 50) -> list[DataHealthCheck]:
    return list(db.scalars(select(DataHealthCheck).order_by(desc(DataHealthCheck.id)).limit(limit)))
