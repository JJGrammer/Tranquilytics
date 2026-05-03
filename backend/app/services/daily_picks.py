"""Daily screened picks from the same model stack as /ticker/preview (cached)."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from app.schemas.market import DailyPickRow
from app.schemas.preview import PreviewResponse
from app.services.advice_policy import BUY, SAFE_BUY
from app.services.report_service import ReportService


def pick_row_from_preview(p: PreviewResponse) -> DailyPickRow | None:
    """
    Include only short-term Safer Buy, or short-term Buy when risk bucket is Low
    (rolling daily-return volatility per risk.py).
    """
    if not p.valid or p.short_term is None:
        return None
    st = p.short_term.tone
    risk = p.risk_level
    if st == SAFE_BUY:
        reason = "Short-term tone: Safer Buy (strongest bullish tier in this policy)."
    elif st == BUY and risk == "Low":
        reason = "Short-term tone: Buy with low volatility bucket (interpreted risk: Low)."
    else:
        return None

    return DailyPickRow(
        symbol=p.symbol,
        name=p.name,
        short_tone=st,
        long_tone=p.long_term.tone if p.long_term else None,
        risk_level=risk,
        confidence=round(float(p.short_term.confidence), 4),
        pick_reason=reason,
    )


def _preview_worker(symbol: str) -> DailyPickRow | None:
    try:
        p = ReportService().preview(symbol)
        return pick_row_from_preview(p)
    except Exception:
        return None


def compute_daily_model_picks(
    symbols: Sequence[str],
    *,
    max_workers: int = 5,
) -> tuple[list[DailyPickRow], datetime]:
    """
    Run preview across ``symbols``; keep rows matching pick policy.
    Large universes (e.g. S&P 500) can take many minutes on a cold cache.
    """
    picks: list[DailyPickRow] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_preview_worker, sym) for sym in symbols]
        for fut in as_completed(futures):
            row = fut.result()
            if row is not None:
                picks.append(row)

    def sort_key(r: DailyPickRow) -> tuple[int, float]:
        safer_first = 0 if r.short_tone == SAFE_BUY else 1
        return (safer_first, -r.confidence)

    picks.sort(key=sort_key)
    return picks, datetime.now(tz=timezone.utc)