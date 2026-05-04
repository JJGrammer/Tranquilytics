from __future__ import annotations

"""
Watchlist HTTP API (local SQLite v1).

Routers stay thin; persistence lives in ``watchlist_repository`` for easy swap to
Postgres/Supabase later (same shapes, different implementation).
"""

from fastapi import APIRouter, Depends, Header, HTTPException

from app.schemas.watchlist import WatchlistAddBody, WatchlistItem, WatchlistListResponse
from app.services.watchlist_repository import (
    DEFAULT_LOCAL_USER_ID,
    SqliteWatchlistRepository,
    get_watchlist_repository,
)

router = APIRouter()


def _resolve_user_id(x_user_id: str | None) -> str:
    raw = (x_user_id or "").strip()
    return raw or DEFAULT_LOCAL_USER_ID


@router.get("", response_model=WatchlistListResponse)
def get_watchlist(
    repo: SqliteWatchlistRepository = Depends(get_watchlist_repository),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> WatchlistListResponse:
    uid = _resolve_user_id(x_user_id)
    rows = repo.list_items(user_id=uid)
    return WatchlistListResponse(
        user_id=uid,
        items=[
            WatchlistItem(symbol=r.symbol, sort_order=r.sort_order, added_at=r.added_at)
            for r in rows
        ],
    )


@router.post("", response_model=WatchlistListResponse)
def add_watchlist_symbol(
    body: WatchlistAddBody,
    repo: SqliteWatchlistRepository = Depends(get_watchlist_repository),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> WatchlistListResponse:
    uid = _resolve_user_id(x_user_id)
    try:
        repo.add(user_id=uid, symbol=body.symbol)
    except ValueError as e:
        msg = str(e)
        if msg == "watchlist full":
            raise HTTPException(status_code=400, detail=msg) from e
        if msg == "duplicate symbol":
            raise HTTPException(status_code=409, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    rows = repo.list_items(user_id=uid)
    return WatchlistListResponse(
        user_id=uid,
        items=[
            WatchlistItem(symbol=r.symbol, sort_order=r.sort_order, added_at=r.added_at)
            for r in rows
        ],
    )


@router.delete("/{symbol}", response_model=WatchlistListResponse)
def remove_watchlist_symbol(
    symbol: str,
    repo: SqliteWatchlistRepository = Depends(get_watchlist_repository),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> WatchlistListResponse:
    uid = _resolve_user_id(x_user_id)
    try:
        removed = repo.remove(user_id=uid, symbol=symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not removed:
        raise HTTPException(status_code=404, detail="symbol not in watchlist")
    rows = repo.list_items(user_id=uid)
    return WatchlistListResponse(
        user_id=uid,
        items=[
            WatchlistItem(symbol=r.symbol, sort_order=r.sort_order, added_at=r.added_at)
            for r in rows
        ],
    )
