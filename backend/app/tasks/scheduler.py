from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.tasks.quote_jobs import get_quote_job_state, run_quote_refresh_job

settings = get_settings()
QUOTE_REFRESH_JOB_ID = "quote_refresh"
_scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def configure_quote_scheduler() -> None:
    if _scheduler.get_job(QUOTE_REFRESH_JOB_ID) is not None:
        return
    _scheduler.add_job(
        run_quote_refresh_job,
        "interval",
        seconds=settings.quote_refresh_interval_seconds,
        id=QUOTE_REFRESH_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={"force": False},
    )


def start_scheduler() -> None:
    configure_quote_scheduler()
    if not _scheduler.running:
        _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def start_scheduler_if_enabled() -> None:
    if settings.enable_quote_scheduler:
        start_scheduler()
    else:
        configure_quote_scheduler()


def get_scheduler_status() -> dict[str, object]:
    job = _scheduler.get_job(QUOTE_REFRESH_JOB_ID)
    return {
        "enabled_by_config": settings.enable_quote_scheduler,
        "running": _scheduler.running,
        "quote_job_registered": job is not None,
        "quote_job_id": QUOTE_REFRESH_JOB_ID if job is not None else None,
        "quote_refresh_interval_seconds": settings.quote_refresh_interval_seconds,
        "skip_non_trading": settings.quote_scheduler_skip_non_trading,
        "next_run_time": job.next_run_time.isoformat() if job is not None and job.next_run_time is not None else None,
        "last_quote_job_state": get_quote_job_state(),
    }


def run_quote_job_now(*, force: bool = True) -> dict[str, object]:
    return run_quote_refresh_job(force=force)
