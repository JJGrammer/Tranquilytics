"""Best daily movers from a curated US large-cap list using yfinance (cached)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import yfinance as yf

from app.schemas.market import DailyLeaderRow

# Curated universe for responsiveness in local demos—not full-exchange breadth.
_LARGE_CAP_TICKERS = sorted(
    {
        'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'AVGO', 'TSLA', 'JPM', 'V', 'UNH',
        'LLY', 'COST', 'WMT', 'HD', 'MA', 'PEP', 'KO', 'BAC', 'ABBV', 'PFE', 'MRK', 'TMUS',
        'ACN', 'CVS', 'ORCL', 'CRM', 'AMD', 'NFLX', 'INTC', 'QCOM', 'CSCO', 'IBM',
    }
)


def _day_change_pct(symbol: str) -> tuple[str, float | None]:
    try:
        h = yf.Ticker(symbol).history(period="7d", interval="1d", auto_adjust=True)
        if h is None or h.empty or len(h) < 2:
            return symbol, None
        close = h["Close"]
        pct = float((close.iloc[-1] / close.iloc[-2] - 1.0) * 100.0)
        return symbol, pct
    except Exception:
        return symbol, None


def _truncate(text: str, max_len: int = 200) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _describe_symbol(symbol: str) -> tuple[str | None, str | None]:
    try:
        t = yf.Ticker(symbol)
        info = getattr(t, "info", None) or {}
        name = info.get("shortName") or info.get("longName")
        blob = info.get("longBusinessSummary") or ""
        desc = _truncate(blob) if blob else None
        return (str(name) if name else None, desc)
    except Exception:
        return None, None


def compute_daily_top_movers(limit: int = 5) -> tuple[list[DailyLeaderRow], datetime | None]:
    """Return top `limit` symbols by latest daily % change in `_LARGE_CAP_TICKERS`."""
    moves: dict[str, float] = {}
    pool = ThreadPoolExecutor(max_workers=10)

    futures = [pool.submit(_day_change_pct, sym) for sym in _LARGE_CAP_TICKERS]
    for fut in as_completed(futures):
        sym, pct = fut.result()
        if pct is not None:
            moves[sym] = pct
    pool.shutdown(wait=True)

    sorted_syms = sorted(moves.keys(), key=lambda s: moves[s], reverse=True)[:limit]
    rows: list[DailyLeaderRow] = []
    as_of: datetime | None = datetime.now(tz=timezone.utc)

    for sym in sorted_syms:
        name, desc = _describe_symbol(sym)
        rows.append(
            DailyLeaderRow(
                symbol=sym,
                change_pct_day=round(moves[sym], 2),
                name=name,
                description=desc,
            )
        )

    return rows, as_of
