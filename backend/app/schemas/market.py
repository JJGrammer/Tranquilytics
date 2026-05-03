from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DailyLeaderRow(BaseModel):
    symbol: str
    change_pct_day: float = Field(description="Approx. latest session vs prior close, %")
    name: str | None = None
    description: str | None = Field(
        default=None,
        description="Short company blurb when yfinance exposes longBusinessSummary",
    )


class DailyLeadersResponse(BaseModel):
    leaders: list[DailyLeaderRow]
    as_of: datetime | None = None
    note: str = Field(
        default="Ranked within a curated large-cap universe (not full market breadth).",
    )


class DailyPickRow(BaseModel):
    symbol: str
    short_tone: str
    risk_level: str
    confidence: float = Field(ge=0.0, le=1.0)
    name: str | None = None
    long_tone: str | None = None
    pick_reason: str = Field(description="Why this row passed the daily screen")


class DailyPicksResponse(BaseModel):
    picks: list[DailyPickRow]
    as_of: datetime | None = None
    note: str = Field(
        default=(
            "Screen: short-term Safer Buy, or short-term Buy with Low volatility bucket, "
            "within the curated universe. Cached; exploratory only—not financial advice."
        ),
    )
