from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    DataFetchLogRead,
    DataHealthCheckRead,
    DataSourceConfigCreate,
    DataSourceConfigRead,
    MarketQuoteRead,
    QuoteRefreshResult,
)
from app.services import market as market_service
from app.services import stocks as stock_service

router = APIRouter()


@router.get("/data-sources", response_model=list[DataSourceConfigRead], summary="查询数据源配置")
def list_data_sources(
    data_type: str | None = Query(default=None, description="按数据类型筛选，如 quote/kline/financial/news"),
    db: Session = Depends(get_db),
):
    return market_service.list_data_source_configs(db, data_type=data_type)


@router.post("/data-sources", response_model=DataSourceConfigRead, status_code=status.HTTP_201_CREATED, summary="新增数据源配置")
def create_data_source(payload: DataSourceConfigCreate, db: Session = Depends(get_db)):
    return market_service.create_data_source_config(db, payload)


@router.get("/data-sources/logs", response_model=list[DataFetchLogRead], summary="查询数据源调用日志")
def list_data_source_logs(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return market_service.list_fetch_logs(db, limit=limit)


@router.get("/data-sources/health", response_model=list[DataHealthCheckRead], summary="查询数据健康检查记录")
def list_data_source_health(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return market_service.list_health_checks(db, limit=limit)


@router.post("/quotes/refresh", response_model=QuoteRefreshResult, summary="刷新股票池行情")
def refresh_quotes(
    provider: str | None = Query(default=None, description="可选：指定 mock/failing 等行情 provider"),
    db: Session = Depends(get_db),
):
    try:
        return market_service.refresh_quotes(db, provider_name=provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/quotes/latest", response_model=list[MarketQuoteRead], summary="查询股票池最新行情")
def list_latest_quotes(db: Session = Depends(get_db)):
    return market_service.list_latest_quotes(db)


@router.get("/stocks/{stock_id}/quote", response_model=MarketQuoteRead, summary="查询单只股票最新行情")
def get_latest_quote(stock_id: int, db: Session = Depends(get_db)):
    stock = stock_service.get_stock(db, stock_id)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="股票不存在")
    quote = market_service.get_latest_quote(db, stock_id)
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该股票暂无行情")
    return quote
