from __future__ import annotations

from pydantic import BaseModel, Field


class HorizonPreview(BaseModel):
    tone: str
    confidence: float = Field(ge=0.0, le=1.0)


class PreviewResponse(BaseModel):
    valid: bool
    symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    risk_level: str = Field(default="Moderate")
    sentiment_label: str = Field(default="Neutral", description="Aggregate headline tilt")
    sentiment_headlines_used: int = Field(default=0, ge=0)
    short_term: HorizonPreview | None = None
    long_term: HorizonPreview | None = None
