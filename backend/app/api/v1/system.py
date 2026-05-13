from fastapi import APIRouter

from app.tasks.scheduler import get_scheduler_status, run_quote_job_now, start_scheduler, stop_scheduler

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/scheduler", summary="查询定时任务状态")
def scheduler_status() -> dict[str, object]:
    return get_scheduler_status()


@router.post("/scheduler/start", summary="启动定时任务")
def scheduler_start() -> dict[str, object]:
    start_scheduler()
    return get_scheduler_status()


@router.post("/scheduler/stop", summary="停止定时任务")
def scheduler_stop() -> dict[str, object]:
    stop_scheduler()
    return get_scheduler_status()


@router.post("/scheduler/quote-refresh/run", summary="立即执行一次行情刷新任务")
def run_quote_refresh(force: bool = True) -> dict[str, object]:
    result = run_quote_job_now(force=force)
    return {"scheduler": get_scheduler_status(), "job_result": result}
