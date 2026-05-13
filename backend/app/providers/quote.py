from datetime import UTC, datetime, timedelta
import importlib
import json
from numbers import Number

from app.models import Stock
from app.schemas import QuotePayload


class QuoteProvider:
    """Base interface for quote providers.

    Implementations should normalize provider-specific fields into QuotePayload so the
    service layer can persist and validate quotes without knowing source-specific schemas.
    """

    name = "base"

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        raise NotImplementedError


def _is_missing(value: object) -> bool:
    return value is None or value == "-" or value == ""


def _to_float(value: object) -> float | None:
    if _is_missing(value):
        return None
    if isinstance(value, Number):
        # NaN is the only common numeric value that is not equal to itself.
        return None if value != value else float(value)
    try:
        text = str(value).replace(",", "").strip()
        return None if text == "" else float(text)
    except ValueError:
        return None


def _to_code(value: object) -> str:
    return str(value).strip().split(".")[0].zfill(6)


def _row_to_dict(row: object) -> dict[str, object]:
    if hasattr(row, "to_dict"):
        return row.to_dict()
    return dict(row)  # type: ignore[arg-type]


def _raw_json(row_data: dict[str, object]) -> str:
    def default(value: object) -> str:
        return str(value)

    return json.dumps(row_data, ensure_ascii=False, default=default)


class AkshareQuoteProvider(QuoteProvider):
    """AKShare realtime A-share quote provider.

    Uses ak.stock_zh_a_spot_em(), which returns the current Shanghai/Shenzhen/Beijing
    A-share quote table from Eastmoney. The provider filters the full table down to
    the requested stock pool and normalizes Chinese columns into QuotePayload.
    """

    name = "akshare"

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        akshare = importlib.import_module("akshare")
        spot_df = akshare.stock_zh_a_spot_em()
        requested_by_code = {_to_code(stock.code): stock for stock in stocks}
        now = datetime.now(UTC).replace(tzinfo=None)
        payloads: list[QuotePayload] = []

        for _, row in spot_df.iterrows():
            row_data = _row_to_dict(row)
            code = _to_code(row_data.get("代码"))
            stock = requested_by_code.get(code)
            if stock is None:
                continue
            payloads.append(
                QuotePayload(
                    symbol=stock.symbol,
                    trade_date=now.date(),
                    quote_time=now,
                    price=_to_float(row_data.get("最新价")),
                    change_amount=_to_float(row_data.get("涨跌额")),
                    change_pct=_to_float(row_data.get("涨跌幅")),
                    volume=_to_float(row_data.get("成交量")),
                    amount=_to_float(row_data.get("成交额")),
                    turnover_rate=_to_float(row_data.get("换手率")),
                    volume_ratio=_to_float(row_data.get("量比")),
                    pe=_to_float(row_data.get("市盈率-动态")),
                    total_market_cap=_to_float(row_data.get("总市值")),
                    float_market_cap=_to_float(row_data.get("流通市值")),
                    raw_data=_raw_json(row_data),
                )
            )
        return payloads


class MockQuoteProvider(QuoteProvider):
    """Deterministic local quote provider for tests and offline development."""

    name = "mock"

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

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        raise RuntimeError("模拟数据源失败")


class MissingPriceQuoteProvider(QuoteProvider):
    """Provider returning structurally valid rows with invalid price data for health checks."""

    name = "missing_price"

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        now = datetime.now(UTC).replace(tzinfo=None)
        return [
            QuotePayload(
                symbol=stock.symbol,
                trade_date=now.date(),
                quote_time=now,
                price=None,
                change_pct=0.0,
                raw_data=f'{{"provider":"missing_price","symbol":"{stock.symbol}"}}',
            )
            for stock in stocks
        ]


class StaleQuoteProvider(QuoteProvider):
    """Provider returning old timestamps to exercise stale-data validation."""

    name = "stale"

    def fetch_quotes(self, stocks: list[Stock]) -> list[QuotePayload]:
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        return [
            QuotePayload(
                symbol=stock.symbol,
                trade_date=old_time.date(),
                quote_time=old_time,
                price=10.0,
                change_pct=0.0,
                volume=1000.0,
                amount=10000.0,
                raw_data=f'{{"provider":"stale","symbol":"{stock.symbol}"}}',
            )
            for stock in stocks
        ]


PROVIDERS: dict[str, type[QuoteProvider]] = {
    AkshareQuoteProvider.name: AkshareQuoteProvider,
    FailingQuoteProvider.name: FailingQuoteProvider,
    MissingPriceQuoteProvider.name: MissingPriceQuoteProvider,
    MockQuoteProvider.name: MockQuoteProvider,
    StaleQuoteProvider.name: StaleQuoteProvider,
}


def get_provider(name: str) -> QuoteProvider:
    provider_class = PROVIDERS.get(name)
    if provider_class is None:
        raise ValueError(f"未知行情数据源：{name}")
    return provider_class()
