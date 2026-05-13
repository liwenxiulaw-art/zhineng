from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import DisciplinePlan, ResearchCard, Stock, Tag
from app.schemas import DisciplinePlanUpsert, ResearchCardUpsert, StockCreate, StockUpdate, TagCreate, TagUpdate


def make_symbol(code: str, exchange: str) -> str:
    return f"{code.strip().upper()}.{exchange.strip().upper()}"


def list_stocks(db: Session, *, active_only: bool = True, tag_id: int | None = None) -> list[Stock]:
    stmt = select(Stock).options(selectinload(Stock.tags)).order_by(Stock.id.desc())
    if active_only:
        stmt = stmt.where(Stock.is_active.is_(True))
    if tag_id is not None:
        stmt = stmt.join(Stock.tags).where(Tag.id == tag_id)
    return list(db.scalars(stmt).unique())


def get_stock(db: Session, stock_id: int) -> Stock | None:
    return db.scalar(select(Stock).options(selectinload(Stock.tags)).where(Stock.id == stock_id))


def create_stock(db: Session, payload: StockCreate) -> Stock:
    tags = list(db.scalars(select(Tag).where(Tag.id.in_(payload.tag_ids)))) if payload.tag_ids else []
    stock = Stock(
        code=payload.code,
        exchange=payload.exchange,
        symbol=make_symbol(payload.code, payload.exchange),
        name=payload.name,
        industry=payload.industry,
        concepts=payload.concepts,
        holding_status=payload.holding_status,
        is_focus=payload.is_focus,
        is_active=payload.is_active,
        tags=tags,
    )
    db.add(stock)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("股票代码和交易所组合已存在，或 symbol 已存在") from exc
    db.refresh(stock)
    return stock


def update_stock(db: Session, stock: Stock, payload: StockUpdate) -> Stock:
    data = payload.model_dump(exclude_unset=True)
    tag_ids = data.pop("tag_ids", None)
    for key, value in data.items():
        setattr(stock, key, value)
    if "code" in data or "exchange" in data:
        stock.symbol = make_symbol(stock.code, stock.exchange)
    if tag_ids is not None:
        stock.tags = list(db.scalars(select(Tag).where(Tag.id.in_(tag_ids)))) if tag_ids else []
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("股票代码和交易所组合已存在，或 symbol 已存在") from exc
    db.refresh(stock)
    return stock


def archive_stock(db: Session, stock: Stock) -> Stock:
    stock.is_active = False
    db.commit()
    db.refresh(stock)
    return stock


def list_tags(db: Session) -> list[Tag]:
    return list(db.scalars(select(Tag).order_by(Tag.category.is_(None), Tag.category.asc(), Tag.name.asc())))


def get_tag(db: Session, tag_id: int) -> Tag | None:
    return db.get(Tag, tag_id)


def create_tag(db: Session, payload: TagCreate) -> Tag:
    tag = Tag(**payload.model_dump())
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("标签名称已存在") from exc
    db.refresh(tag)
    return tag


def update_tag(db: Session, tag: Tag, payload: TagUpdate) -> Tag:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tag, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("标签名称已存在") from exc
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag: Tag) -> None:
    db.delete(tag)
    db.commit()


def add_tag_to_stock(db: Session, stock: Stock, tag: Tag) -> Stock:
    if tag not in stock.tags:
        stock.tags.append(tag)
        db.commit()
    db.refresh(stock)
    return stock


def remove_tag_from_stock(db: Session, stock: Stock, tag: Tag) -> Stock:
    if tag in stock.tags:
        stock.tags.remove(tag)
        db.commit()
    db.refresh(stock)
    return stock


def get_research_card(db: Session, stock_id: int) -> ResearchCard | None:
    return db.scalar(select(ResearchCard).where(ResearchCard.stock_id == stock_id))


def upsert_research_card(db: Session, stock_id: int, payload: ResearchCardUpsert) -> ResearchCard:
    card = get_research_card(db, stock_id)
    if card is None:
        card = ResearchCard(stock_id=stock_id, **payload.model_dump())
        db.add(card)
    else:
        for key, value in payload.model_dump().items():
            setattr(card, key, value)
    db.commit()
    db.refresh(card)
    return card


def get_discipline_plan(db: Session, stock_id: int) -> DisciplinePlan | None:
    return db.scalar(select(DisciplinePlan).where(DisciplinePlan.stock_id == stock_id))


def upsert_discipline_plan(db: Session, stock_id: int, payload: DisciplinePlanUpsert) -> DisciplinePlan:
    plan = get_discipline_plan(db, stock_id)
    if plan is None:
        plan = DisciplinePlan(stock_id=stock_id, **payload.model_dump())
        db.add(plan)
    else:
        for key, value in payload.model_dump().items():
            setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return plan
