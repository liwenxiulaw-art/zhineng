from datetime import UTC, datetime, timedelta

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
