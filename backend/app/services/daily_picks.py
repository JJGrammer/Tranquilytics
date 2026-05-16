"""Daily screened picks from the same model stack as /ticker/preview (cached)."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Literal

from app.schemas.market import DailyPickRow
from app.schemas.preview import PreviewResponse
from app.services.advice_policy import BUY, SAFE_BUY
from app.services.report_service import ReportService
from yfinance.exceptions import YFRateLimitError

PickFocus = Literal["short", "long"]


def pick_row_from_preview(
    p: PreviewResponse,
    *,
    focus: PickFocus = "short",
) -> DailyPickRow | None:
    """
    Same policy as the short-term model screen, optionally applied to **long-term** tones:

    - Safer Buy on the chosen horizon, or
    - Buy on that horizon when interpreted risk is Low (rolling vol bucket).
    """
    if not p.valid:
        return None
    risk = p.risk_level
    short_label = p.short_term.tone if p.short_term else "Neutral"
    long_label = p.long_term.tone if p.long_term else None

    if focus == "short":
        if p.short_term is None:
            return None
        st = p.short_term.tone
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
            long_tone=long_label,
            risk_level=risk,
            confidence=round(float(p.short_term.confidence), 4),
            screen_tone=st,
            screen_horizon="short",
            pick_reason=reason,
        )

    if p.long_term is None:
        return None
    lt = p.long_term.tone
    if lt == SAFE_BUY:
        reason = "Long-term tone: Safer Buy (strongest bullish tier in this policy)."
    elif lt == BUY and risk == "Low":
        reason = "Long-term tone: Buy with low volatility bucket (interpreted risk: Low)."
    else:
        return None
    return DailyPickRow(
        symbol=p.symbol,
        name=p.name,
        short_tone=short_label,
        long_tone=lt,
        risk_level=risk,
        confidence=round(float(p.long_term.confidence), 4),
        screen_tone=lt,
        screen_horizon="long",
        pick_reason=reason,
    )


def _preview_worker(
    symbol: str,
    focus: PickFocus,
    *,
    bypass_preview_cache: bool,
) -> DailyPickRow | None:
    """
    Run one ``preview(..., screen_mode=True)`` and map to a pick row if policy matches.

    Swallows per-symbol failures so one bad ticker does not abort the scan.
    **Does not** swallow Yahoo rate limits — those propagate so the API can return 503.
    """
    try:
        p = ReportService().preview(
            symbol,
            bypass_cache=bypass_preview_cache,
            screen_mode=True,
        )
        return pick_row_from_preview(p, focus=focus)
    except YFRateLimitError:
        raise
    except Exception:
        return None


def compute_daily_model_picks(
    symbols: Sequence[str],
    *,
    max_workers: int = 5,
    focus: PickFocus = "short",
    bypass_preview_cache: bool = False,
) -> tuple[list[DailyPickRow], datetime]:
    """
    Run preview across ``symbols``; keep rows matching pick policy for ``focus``.
    Large universes (e.g. S&P 500) can take many minutes on a cold cache.

    Uses ``screen_mode`` previews (no Google RSS / company blurb) plus per-symbol cache ~20m
    unless ``bypass_preview_cache=True``.

    Raises:
        YFRateLimitError: If Yahoo throttles any worker thread — surfaces to FastAPI as 503.
    """
    picks: list[DailyPickRow] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(
                _preview_worker,
                sym,
                focus,
                bypass_preview_cache=bypass_preview_cache,
            )
            for sym in symbols
        ]
        for fut in as_completed(futures):
            try:
                row = fut.result()
            except YFRateLimitError:
                raise
            if row is not None:
                picks.append(row)

    def sort_key(r: DailyPickRow) -> tuple[int, float]:
        safer_first = 0 if r.screen_tone == SAFE_BUY else 1
        return (safer_first, -r.confidence)

    picks.sort(key=sort_key)
    return picks, datetime.now(tz=timezone.utc)
