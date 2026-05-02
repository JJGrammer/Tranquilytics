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
    short_term: HorizonPreview | None = None
    long_term: HorizonPreview | None = None
