from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Citation(BaseModel):
    kind: str = Field(description="e.g. market_data, technical_features")
    source: str = Field(description="Human readable data source")
    as_of: datetime | None = None


class HorizonAdvice(BaseModel):
    horizon: str = Field(description="short or long")
    window_trading_days: int
    tone: str = Field(description="Safer Buy | Buy | Neutral | Sell | Sell Soon")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="Plain-language rationale for this horizon")
    expected_return: float | None = Field(
        default=None, description="Model-estimated directional bias over horizon"
    )
    volatility: float | None = Field(default=None, description="Estimated daily volatility")


class ReportRequest(BaseModel):
    symbol: str
    include_citations: bool = True


class ReportResponse(BaseModel):
    symbol: str
    name: str | None = None
    currency: str | None = None
    exchange: str | None = None

    generated_at: datetime
    as_of: datetime | None = None

    risk_level: str = Field(description="Low | Moderate | High")

    short_term: HorizonAdvice
    long_term: HorizonAdvice

    summary: str
    disclaimer: str
    citations: list[Citation] = []
