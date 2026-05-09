from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HoldingStatus = Literal["watching", "holding", "cleared", "archived"]
Exchange = Literal["SH", "SZ", "BJ"]


class TagBase(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=32)
    description: str | None = None


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=32)
    description: str | None = None


class TagRead(TagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class StockBase(BaseModel):
    code: str = Field(min_length=6, max_length=16, examples=["600519"])
    exchange: Exchange
    name: str = Field(min_length=1, max_length=128)
    industry: str | None = Field(default=None, max_length=128)
    concepts: str | None = None
    holding_status: HoldingStatus = "watching"
    is_focus: bool = False
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str) -> str:
        return value.strip().upper()


class StockCreate(StockBase):
    tag_ids: list[int] = Field(default_factory=list)


class StockUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=6, max_length=16)
    exchange: Exchange | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    industry: str | None = Field(default=None, max_length=128)
    concepts: str | None = None
    holding_status: HoldingStatus | None = None
    is_focus: bool | None = None
    is_active: bool | None = None
    tag_ids: list[int] | None = None


class StockRead(StockBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    tags: list[TagRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ResearchCardBase(BaseModel):
    investment_thesis: str | None = None
    core_business: str | None = None
    industry_position: str | None = None
    catalysts: str | None = None
    risk_points: str | None = None
    key_observation_metrics: str | None = None
    competitors: str | None = None
    has_earnings_support: bool | None = None
    has_policy_driver: bool | None = None
    has_theme_speculation: bool | None = None
    manual_note: str | None = None
    ai_summary: str | None = None
    ai_updated_at: datetime | None = None


class ResearchCardUpsert(ResearchCardBase):
    pass


class ResearchCardRead(ResearchCardBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    created_at: datetime
    updated_at: datetime


class DisciplinePlanBase(BaseModel):
    target_buy_price: float | None = Field(default=None, ge=0)
    target_sell_price: float | None = Field(default=None, ge=0)
    stop_loss_price: float | None = Field(default=None, ge=0)
    position_plan: str | None = None
    max_drawdown_pct: float | None = Field(default=None, ge=0)
    allow_chasing_high: bool = False
    plan_reason: str | None = None
    is_active: bool = True


class DisciplinePlanUpsert(DisciplinePlanBase):
    pass


class DisciplinePlanRead(DisciplinePlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    created_at: datetime
    updated_at: datetime
