from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import create_db_and_tables
from app.tasks.scheduler import start_scheduler_if_enabled, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    start_scheduler_if_enabled()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="本地优先的 A 股个人投资研究辅助系统后端 API。",
    lifespan=lifespan,
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
