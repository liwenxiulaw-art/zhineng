from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    DisciplinePlanRead,
    DisciplinePlanUpsert,
    ResearchCardRead,
    ResearchCardUpsert,
    StockCreate,
    StockRead,
    StockUpdate,
    TagCreate,
    TagRead,
    TagUpdate,
)
from app.services import stocks as stock_service

router = APIRouter()


def _get_stock_or_404(db: Session, stock_id: int):
    stock = stock_service.get_stock(db, stock_id)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="股票不存在")
    return stock


def _get_tag_or_404(db: Session, tag_id: int):
    tag = stock_service.get_tag(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return tag


@router.get("/stocks", response_model=list[StockRead], summary="查询股票池")
def list_stocks(
    active_only: bool = Query(default=True, description="是否只返回仍在股票池中的股票"),
    tag_id: int | None = Query(default=None, description="按标签 ID 筛选"),
    db: Session = Depends(get_db),
):
    return stock_service.list_stocks(db, active_only=active_only, tag_id=tag_id)


@router.post("/stocks", response_model=StockRead, status_code=status.HTTP_201_CREATED, summary="新增股票")
def create_stock(payload: StockCreate, db: Session = Depends(get_db)):
    try:
        return stock_service.create_stock(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/stocks/{stock_id}", response_model=StockRead, summary="查询单只股票")
def get_stock(stock_id: int, db: Session = Depends(get_db)):
    return _get_stock_or_404(db, stock_id)


@router.put("/stocks/{stock_id}", response_model=StockRead, summary="更新股票")
def update_stock(stock_id: int, payload: StockUpdate, db: Session = Depends(get_db)):
    stock = _get_stock_or_404(db, stock_id)
    try:
        return stock_service.update_stock(db, stock, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/stocks/{stock_id}", response_model=StockRead, summary="从股票池归档股票")
def archive_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = _get_stock_or_404(db, stock_id)
    return stock_service.archive_stock(db, stock)


@router.get("/tags", response_model=list[TagRead], summary="查询标签")
def list_tags(db: Session = Depends(get_db)):
    return stock_service.list_tags(db)


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED, summary="新增标签")
def create_tag(payload: TagCreate, db: Session = Depends(get_db)):
    try:
        return stock_service.create_tag(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/tags/{tag_id}", response_model=TagRead, summary="更新标签")
def update_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)):
    tag = _get_tag_or_404(db, tag_id)
    try:
        return stock_service.update_tag(db, tag, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除标签")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = _get_tag_or_404(db, tag_id)
    stock_service.delete_tag(db, tag)
    return None


@router.post("/stocks/{stock_id}/tags/{tag_id}", response_model=StockRead, summary="为股票绑定标签")
def add_tag_to_stock(stock_id: int, tag_id: int, db: Session = Depends(get_db)):
    stock = _get_stock_or_404(db, stock_id)
    tag = _get_tag_or_404(db, tag_id)
    return stock_service.add_tag_to_stock(db, stock, tag)


@router.delete("/stocks/{stock_id}/tags/{tag_id}", response_model=StockRead, summary="移除股票标签")
def remove_tag_from_stock(stock_id: int, tag_id: int, db: Session = Depends(get_db)):
    stock = _get_stock_or_404(db, stock_id)
    tag = _get_tag_or_404(db, tag_id)
    return stock_service.remove_tag_from_stock(db, stock, tag)


@router.get("/stocks/{stock_id}/research-card", response_model=ResearchCardRead, summary="查询投资逻辑卡片")
def get_research_card(stock_id: int, db: Session = Depends(get_db)):
    _get_stock_or_404(db, stock_id)
    card = stock_service.get_research_card(db, stock_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="投资逻辑卡片不存在")
    return card


@router.put("/stocks/{stock_id}/research-card", response_model=ResearchCardRead, summary="创建或更新投资逻辑卡片")
def upsert_research_card(stock_id: int, payload: ResearchCardUpsert, db: Session = Depends(get_db)):
    _get_stock_or_404(db, stock_id)
    return stock_service.upsert_research_card(db, stock_id, payload)


@router.get("/stocks/{stock_id}/discipline-plan", response_model=DisciplinePlanRead, summary="查询交易纪律计划")
def get_discipline_plan(stock_id: int, db: Session = Depends(get_db)):
    _get_stock_or_404(db, stock_id)
    plan = stock_service.get_discipline_plan(db, stock_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="交易纪律计划不存在")
    return plan


@router.put("/stocks/{stock_id}/discipline-plan", response_model=DisciplinePlanRead, summary="创建或更新交易纪律计划")
def upsert_discipline_plan(stock_id: int, payload: DisciplinePlanUpsert, db: Session = Depends(get_db)):
    _get_stock_or_404(db, stock_id)
    return stock_service.upsert_discipline_plan(db, stock_id, payload)
