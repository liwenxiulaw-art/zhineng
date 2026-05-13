from functools import lru_cache
from pathlib import Path
import os


class Settings:
    """Application settings loaded from environment variables."""

    app_name: str = os.getenv("APP_NAME", "A 股股票跟踪系统 API")
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parents[3] / 'data' / 'app.db'}",
    )
    echo_sql: bool = os.getenv("ECHO_SQL", "false").lower() in {"1", "true", "yes"}
    quote_stale_seconds: int = int(os.getenv("QUOTE_STALE_SECONDS", "300"))
    quote_refresh_interval_seconds: int = int(os.getenv("QUOTE_REFRESH_INTERVAL_SECONDS", "15"))
    enable_quote_scheduler: bool = os.getenv("ENABLE_QUOTE_SCHEDULER", "false").lower() in {"1", "true", "yes"}
    quote_scheduler_skip_non_trading: bool = os.getenv("QUOTE_SCHEDULER_SKIP_NON_TRADING", "true").lower() in {"1", "true", "yes"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
