from __future__ import annotations

from fastapi import APIRouter

from app.schemas.market import DailyLeadersResponse
from app.services.cache import SqliteCache
from app.services.daily_leaders import compute_daily_top_movers

router = APIRouter()


@router.get("/daily-leaders", response_model=DailyLeadersResponse)
def daily_leaders(limit: int = 5) -> DailyLeadersResponse:
    """Top daily % movers within Tranquilytics' curated universe (cached ~3 min)."""
    limit_i = max(1, min(int(limit), 15))
    cache_key = f"market:daily_leaders:{limit_i}"
    cache = SqliteCache()
    hit = cache.get(cache_key)
    if hit:
        return DailyLeadersResponse.model_validate(hit.value)

    leaders, as_of = compute_daily_top_movers(limit=limit_i)
    body = DailyLeadersResponse(leaders=leaders, as_of=as_of)
    cache.set(cache_key, body.model_dump(mode="json"), ttl_seconds=180)
    return body
