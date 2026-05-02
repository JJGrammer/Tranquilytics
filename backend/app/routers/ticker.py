from __future__ import annotations

"""
Ticker-related endpoints.

Primary goal:
- Validate that a symbol exists and return basic metadata (name/exchange/currency).

Why this exists:
- Keeps the frontend UX responsive: validate early, then enable "Generate report".
- Provides a single place to swap/extend data providers later (yfinance -> +AlphaVantage).
"""

from fastapi import APIRouter, HTTPException

from app.schemas.preview import PreviewResponse
from app.schemas.ticker import TickerValidateResponse
from app.services.market_data import MarketDataService
from app.services.report_service import ReportService

router = APIRouter()


@router.get("/validate", response_model=TickerValidateResponse)
def validate_ticker(symbol: str) -> TickerValidateResponse:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    md = MarketDataService()
    info = md.try_get_ticker_info(symbol)
    if info is None:
        return TickerValidateResponse(valid=False, symbol=symbol)

    return TickerValidateResponse(
        valid=True,
        symbol=symbol,
        name=info.get("name"),
        exchange=info.get("exchange"),
        currency=info.get("currency"),
    )


@router.get("/preview", response_model=PreviewResponse)
def preview_ticker(symbol: str) -> PreviewResponse:
    """Dashboard quick read: tones + risk without loading the full narrative report."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    return ReportService().preview(symbol)

