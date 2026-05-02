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
