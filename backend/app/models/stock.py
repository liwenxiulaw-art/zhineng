from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class StockTag(Base):
    __tablename__ = "stock_tags"
    __table_args__ = (UniqueConstraint("stock_id", "tag_id", name="uq_stock_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Stock(TimestampMixin, Base):
    __tablename__ = "stocks"
    __table_args__ = (UniqueConstraint("code", "exchange", name="uq_stock_code_exchange"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128))
    concepts: Mapped[str | None] = mapped_column(Text)
    holding_status: Mapped[str] = mapped_column(String(32), default="watching", nullable=False)
    is_focus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    research_card: Mapped["ResearchCard | None"] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        uselist=False,
    )
    discipline_plan: Mapped["DisciplinePlan | None"] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        uselist=False,
    )
    tags: Mapped[list["Tag"]] = relationship(secondary="stock_tags", back_populates="stocks")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    color: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    stocks: Mapped[list[Stock]] = relationship(secondary="stock_tags", back_populates="tags")


class ResearchCard(TimestampMixin, Base):
    __tablename__ = "stock_research_cards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), unique=True, nullable=False)
    investment_thesis: Mapped[str | None] = mapped_column(Text)
    core_business: Mapped[str | None] = mapped_column(Text)
    industry_position: Mapped[str | None] = mapped_column(Text)
    catalysts: Mapped[str | None] = mapped_column(Text)
    risk_points: Mapped[str | None] = mapped_column(Text)
    key_observation_metrics: Mapped[str | None] = mapped_column(Text)
    competitors: Mapped[str | None] = mapped_column(Text)
    has_earnings_support: Mapped[bool | None] = mapped_column(Boolean)
    has_policy_driver: Mapped[bool | None] = mapped_column(Boolean)
    has_theme_speculation: Mapped[bool | None] = mapped_column(Boolean)
    manual_note: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    stock: Mapped[Stock] = relationship(back_populates="research_card")


class DisciplinePlan(TimestampMixin, Base):
    __tablename__ = "stock_discipline_plans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), unique=True, nullable=False)
    target_buy_price: Mapped[float | None] = mapped_column(Float)
    target_sell_price: Mapped[float | None] = mapped_column(Float)
    stop_loss_price: Mapped[float | None] = mapped_column(Float)
    position_plan: Mapped[str | None] = mapped_column(Text)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float)
    allow_chasing_high: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plan_reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stock: Mapped[Stock] = relationship(back_populates="discipline_plan")
