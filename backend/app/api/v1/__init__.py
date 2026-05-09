from fastapi import APIRouter

from app.api.v1.stocks import router as stocks_router

api_router = APIRouter()
api_router.include_router(stocks_router)
