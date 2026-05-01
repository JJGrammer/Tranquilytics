from __future__ import annotations

from pydantic import BaseModel


class TickerValidateResponse(BaseModel):
    valid: bool
    symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None

