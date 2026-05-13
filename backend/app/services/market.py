from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DataFetchLog, DataHealthCheck, DataSourceConfig, MarketQuote, Stock
from app.providers import get_provider
from app.schemas import DataSourceConfigCreate, QuotePayload
from app.schemas.market import QuoteHealthIssue, QuoteRefreshResult

settings = get_settings()


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


def get_quote_source_candidates(db: Session, *, provider_name: str | None = None) -> list[DataSourceConfig]:
    if provider_name is not None:
        get_provider(provider_name)
        return [DataSourceConfig(provider=provider_name, data_type="quote", priority=0, is_enabled=True)]

    ensure_default_quote_source(db)
    return list(
        db.scalars(
            select(DataSourceConfig)
            .where(DataSourceConfig.data_type == "quote", DataSourceConfig.is_enabled.is_(True))
            .order_by(DataSourceConfig.priority.asc(), DataSourceConfig.id.asc())
        )
    )


def _quote_health(payload: QuotePayload, *, expected_symbol: str, now: datetime | None = None) -> QuoteHealthIssue:
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    if payload.symbol != expected_symbol:
        return QuoteHealthIssue(
            status="abnormal",
            issue_type="symbol_mismatch",
            issue_detail=f"返回代码 {payload.symbol} 与请求代码 {expected_symbol} 不一致",
        )
    if payload.price is None:
        return QuoteHealthIssue(status="abnormal", issue_type="price_missing", issue_detail="当前价为空")
    if payload.price <= 0:
        return QuoteHealthIssue(status="abnormal", issue_type="price_invalid", issue_detail="当前价小于或等于 0")
    if payload.change_pct is not None and abs(payload.change_pct) > 35:
        return QuoteHealthIssue(status="abnormal", issue_type="change_pct_outlier", issue_detail="涨跌幅超出合理校验阈值")
    if payload.quote_time is None:
        return QuoteHealthIssue(status="partial", issue_type="timestamp_missing", issue_detail="行情时间为空")
    age_seconds = (current_time - payload.quote_time).total_seconds()
    if age_seconds > settings.quote_stale_seconds:
        return QuoteHealthIssue(status="stale", issue_type="timestamp_stale", issue_detail="行情时间超过 stale 阈值")
    missing_fields = []
    if payload.change_pct is None:
        missing_fields.append("change_pct")
    if payload.volume is None:
        missing_fields.append("volume")
    if payload.amount is None:
        missing_fields.append("amount")
    if missing_fields:
        return QuoteHealthIssue(
            status="partial",
            issue_type="field_missing",
            issue_detail=f"关键字段缺失：{', '.join(missing_fields)}",
        )
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


def _persist_quote_payloads(
    db: Session,
    *,
    stocks: list[Stock],
    payloads: list[QuotePayload],
    provider_name: str,
    source_priority: int,
    is_fallback: bool,
) -> tuple[int, list[str], list[str]]:
    payload_by_symbol = {payload.symbol: payload for payload in payloads}
    refreshed_count = 0
    failed_symbols: list[str] = []
    statuses: list[str] = []
    now = datetime.now(UTC).replace(tzinfo=None)

    for stock in stocks:
        payload = payload_by_symbol.get(stock.symbol)
        if payload is None:
            failed_symbols.append(stock.symbol)
            db.add(
                DataHealthCheck(
                    data_type="quote",
                    stock_id=stock.id,
                    provider=provider_name,
                    status="missing",
                    issue_type="quote_missing",
                    issue_detail="数据源未返回该股票行情",
                )
            )
            statuses.append("missing")
            continue

        issue = _quote_health(payload, expected_symbol=stock.symbol, now=now)
        db.add(
            MarketQuote(
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
                source=provider_name,
                source_priority=source_priority,
                is_fallback=is_fallback,
                data_status=issue.status,
                abnormal_reason=issue.issue_detail,
                raw_data=payload.raw_data,
            )
        )
        db.add(
            DataHealthCheck(
                data_type="quote",
                stock_id=stock.id,
                provider=provider_name,
                status=issue.status,
                issue_type=issue.issue_type,
                issue_detail=issue.issue_detail,
                last_valid_data_at=payload.quote_time if issue.status == "normal" else None,
            )
        )
        refreshed_count += 1
        statuses.append(issue.status)

    db.commit()
    return refreshed_count, failed_symbols, statuses


def _overall_status(statuses: list[str], refreshed_count: int) -> str:
    if refreshed_count == 0:
        return "missing"
    if statuses and all(status == "normal" for status in statuses):
        return "normal"
    if any(status == "abnormal" for status in statuses):
        return "abnormal"
    if any(status == "stale" for status in statuses):
        return "stale"
    return "partial"


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
        return QuoteRefreshResult(
            provider=log.provider,
            is_fallback=False,
            data_status="missing",
            refreshed_count=0,
            fetch_log_id=log.id,
            attempted_providers=[log.provider],
        )

    candidates = get_quote_source_candidates(db, provider_name=provider_name)
    request_key = ",".join(stock.symbol for stock in stocks)
    attempted_providers: list[str] = []
    failed_symbols = [stock.symbol for stock in stocks]
    last_log: DataFetchLog | None = None

    for index, config in enumerate(candidates):
        provider = get_provider(config.provider)
        attempted_providers.append(provider.name)
        started_at = datetime.now(UTC).replace(tzinfo=None)
        used_fallback = index > 0
        try:
            payloads = provider.fetch_quotes(stocks)
        except Exception as exc:
            last_log = _write_fetch_log(
                db,
                provider=provider.name,
                endpoint="fetch_quotes",
                request_key=request_key,
                status="failed",
                started_at=started_at,
                records_count=0,
                used_fallback=used_fallback,
                error_message=str(exc),
            )
            continue

        refreshed_count, failed_symbols, statuses = _persist_quote_payloads(
            db,
            stocks=stocks,
            payloads=payloads,
            provider_name=provider.name,
            source_priority=config.priority,
            is_fallback=used_fallback,
        )
        last_log = _write_fetch_log(
            db,
            provider=provider.name,
            endpoint="fetch_quotes",
            request_key=request_key,
            status="fallback" if used_fallback else "success",
            started_at=started_at,
            records_count=refreshed_count,
            used_fallback=used_fallback,
        )
        return QuoteRefreshResult(
            provider=provider.name,
            is_fallback=used_fallback,
            data_status=_overall_status(statuses, refreshed_count),
            refreshed_count=refreshed_count,
            failed_symbols=failed_symbols,
            fetch_log_id=last_log.id,
            attempted_providers=attempted_providers,
        )

    return QuoteRefreshResult(
        provider=attempted_providers[-1] if attempted_providers else "none",
        is_fallback=len(attempted_providers) > 1,
        data_status="abnormal",
        refreshed_count=0,
        failed_symbols=failed_symbols,
        fetch_log_id=last_log.id if last_log is not None else None,
        attempted_providers=attempted_providers,
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
