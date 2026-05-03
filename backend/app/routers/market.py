from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.schemas.market import DailyLeadersResponse, DailyPicksResponse
from app.services.cache import SqliteCache
from app.services.daily_leaders import CURATED_LARGE_CAP_UNIVERSE, compute_daily_top_movers
from app.services.daily_picks import compute_daily_model_picks
from app.services.sp500_universe import SP500_TICKERS

router = APIRouter()


@router.get("/daily-leaders", response_model=DailyLeadersResponse)
def daily_leaders(limit: int = 5) -> DailyLeadersResponse:
    """Top daily % movers within Tranquilytics' curated universe (cached ~3 min)."""
    limit_i = max(1, min(int(limit), 12))
    cache_key = f"market:daily_leaders:{limit_i}"
    cache = SqliteCache()
    hit = cache.get(cache_key)
    if hit:
        return DailyLeadersResponse.model_validate(hit.value)

    leaders, as_of = compute_daily_top_movers(limit=limit_i)
    body = DailyLeadersResponse(leaders=leaders, as_of=as_of)
    cache.set(cache_key, body.model_dump(mode="json"), ttl_seconds=180)
    return body


@router.get("/daily-picks", response_model=DailyPicksResponse)
def daily_picks(
    universe: Literal["sp500", "curated"] = Query(
        "sp500",
        description="sp500: full S&P 500 list (~503). curated: small demo basket (faster).",
    ),
    refresh: bool = Query(
        False,
        description="If true, recompute even when a cached response exists (slow for sp500).",
    ),
) -> DailyPicksResponse:
    """
    Model-screened names: short-term Safer Buy, or Buy with Low volatility.
    Default universe is S&P 500; responses are cached ~24h per universe.
    """
    syms: tuple[str, ...] = SP500_TICKERS if universe == "sp500" else tuple(CURATED_LARGE_CAP_UNIVERSE)
    cache_key = f"market:daily_picks:{universe}:v2"
    cache = SqliteCache()
    if not refresh:
        hit = cache.get(cache_key)
        if hit is not None:
            return DailyPicksResponse.model_validate(hit.value)

    workers = 6 if len(syms) > 120 else 5
    rows, as_of = compute_daily_model_picks(syms, max_workers=workers)
    note = (
        f"Universe {universe}: scanned {len(syms)} symbols with the same stack as /ticker/preview. "
        "Includes short-term Safer Buy, or Buy when interpreted risk is Low. "
        "First uncached S&P 500 run can take many minutes. Exploratory only—not financial advice."
    )
    body = DailyPicksResponse(picks=rows, as_of=as_of, note=note)
    cache.set(cache_key, body.model_dump(mode="json"), ttl_seconds=86_400)
    return body
