from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistItem(BaseModel):
    symbol: str
    sort_order: int = Field(ge=0)
    added_at: datetime


class WatchlistListResponse(BaseModel):
    """Watchlist for one user partition (local default today; host maps auth → user_id later)."""

    user_id: str = Field(description="Partition key; use 'local' until auth exists.")
    items: list[WatchlistItem]
    max_items: int = Field(default=50, description="Server-side cap (requirement: ≥10 slots).")


class WatchlistAddBody(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
