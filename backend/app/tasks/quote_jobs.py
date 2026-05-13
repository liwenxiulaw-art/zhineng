from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.market import refresh_quotes
from app.utils.trading_time import is_a_share_continuous_auction_time

settings = get_settings()
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

_LAST_QUOTE_JOB_STATE: dict[str, object] = {
    "last_run_at": None,
    "last_status": "never_run",
    "last_message": None,
    "last_result": None,
}


def get_quote_job_state() -> dict[str, object]:
    return dict(_LAST_QUOTE_JOB_STATE)


def run_quote_refresh_job(*, force: bool = False) -> dict[str, object]:
    """Refresh quotes for the active stock pool and keep a small in-memory status snapshot."""

    now_utc = datetime.now(UTC)
    now_local = now_utc.astimezone(SHANGHAI_TZ)
    _LAST_QUOTE_JOB_STATE["last_run_at"] = now_utc.replace(tzinfo=None).isoformat()

    if settings.quote_scheduler_skip_non_trading and not force and not is_a_share_continuous_auction_time(now_local):
        _LAST_QUOTE_JOB_STATE["last_status"] = "skipped"
        _LAST_QUOTE_JOB_STATE["last_message"] = "非 A 股连续竞价时段，跳过本次行情刷新"
        _LAST_QUOTE_JOB_STATE["last_result"] = None
        return get_quote_job_state()

    db = SessionLocal()
    try:
        result = refresh_quotes(db)
    except Exception as exc:
        _LAST_QUOTE_JOB_STATE["last_status"] = "failed"
        _LAST_QUOTE_JOB_STATE["last_message"] = str(exc)
        _LAST_QUOTE_JOB_STATE["last_result"] = None
    else:
        _LAST_QUOTE_JOB_STATE["last_status"] = "success"
        _LAST_QUOTE_JOB_STATE["last_message"] = None
        _LAST_QUOTE_JOB_STATE["last_result"] = result.model_dump()
    finally:
        db.close()

    return get_quote_job_state()
