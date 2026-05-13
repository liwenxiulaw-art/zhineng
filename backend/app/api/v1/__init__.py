from fastapi import APIRouter

from app.api.v1.market import router as market_router
from app.api.v1.stocks import router as stocks_router
from app.api.v1.system import router as system_router

api_router = APIRouter()
api_router.include_router(stocks_router)
api_router.include_router(market_router)
api_router.include_router(system_router)
