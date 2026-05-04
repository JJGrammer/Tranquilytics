"""
Persistent watchlist storage (local SQLite v1).

Migration notes:
- Every row is keyed by ``user_id`` so a future hosted API can map JWT / Supabase uid
  to the same schema without a rewrite.
- Swap this module's concrete class for an HTTP-backed repository that speaks the same
  methods; keep FastAPI routers thin.
- Default db path is separate from ``SqliteCache`` (TTL cache) to avoid mixing concerns.
"""

from __future__ import annotations

import os
import re
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Single-user local dev until auth exists.
DEFAULT_LOCAL_USER_ID = "local"
_MAX_ITEMS = 50
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,14}$")


def default_state_db_path() -> str:
    raw = os.environ.get("TRANQUILYTICS_STATE_DB", "").strip()
    if raw:
        return str(Path(raw))
    return str(Path("app/local_state.db"))


def normalize_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not _SYMBOL_RE.match(s):
        raise ValueError("invalid symbol format")
    return s


@dataclass(frozen=True)
class WatchlistRow:
    symbol: str
    sort_order: int
    added_at: datetime


class WatchlistRepository(ABC):
    @abstractmethod
    def list_items(self, *, user_id: str) -> list[WatchlistRow]:
        raise NotImplementedError

    @abstractmethod
    def add(self, *, user_id: str, symbol: str) -> WatchlistRow:
        raise NotImplementedError

    @abstractmethod
    def remove(self, *, user_id: str, symbol: str) -> bool:
        raise NotImplementedError


class SqliteWatchlistRepository(WatchlistRepository):
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or default_state_db_path()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    def _init(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist_item (
                  user_id TEXT NOT NULL,
                  symbol TEXT NOT NULL,
                  sort_order INTEGER NOT NULL,
                  added_at TEXT NOT NULL,
                  PRIMARY KEY (user_id, symbol)
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_watchlist_user_sort "
                "ON watchlist_item(user_id, sort_order)"
            )
            con.commit()

    def list_items(self, *, user_id: str) -> list[WatchlistRow]:
        uid = user_id.strip() or DEFAULT_LOCAL_USER_ID
        with closing(self._connect()) as con:
            cur = con.execute(
                """
                SELECT symbol, sort_order, added_at
                FROM watchlist_item
                WHERE user_id = ?
                ORDER BY sort_order ASC, symbol ASC
                """,
                (uid,),
            )
            rows = cur.fetchall()
        out: list[WatchlistRow] = []
        for sym, order, added in rows:
            out.append(
                WatchlistRow(
                    symbol=str(sym),
                    sort_order=int(order),
                    added_at=datetime.fromisoformat(str(added)),
                )
            )
        return out

    def add(self, *, user_id: str, symbol: str) -> WatchlistRow:
        sym = normalize_symbol(symbol)
        uid = user_id.strip() or DEFAULT_LOCAL_USER_ID
        now = datetime.now(tz=timezone.utc).isoformat()
        with closing(self._connect()) as con:
            count = int(
                con.execute(
                    "SELECT COUNT(*) FROM watchlist_item WHERE user_id = ?",
                    (uid,),
                ).fetchone()[0]
            )
            if count >= _MAX_ITEMS:
                raise ValueError("watchlist full")
            exists = con.execute(
                "SELECT 1 FROM watchlist_item WHERE user_id = ? AND symbol = ?",
                (uid, sym),
            ).fetchone()
            if exists:
                raise ValueError("duplicate symbol")
            row_mx = con.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM watchlist_item WHERE user_id = ?",
                (uid,),
            ).fetchone()
            next_order = int(row_mx[0]) + 1
            con.execute(
                """
                INSERT INTO watchlist_item(user_id, symbol, sort_order, added_at)
                VALUES(?, ?, ?, ?)
                """,
                (uid, sym, next_order, now),
            )
            con.commit()
        return WatchlistRow(symbol=sym, sort_order=next_order, added_at=datetime.fromisoformat(now))

    def remove(self, *, user_id: str, symbol: str) -> bool:
        sym = normalize_symbol(symbol)
        uid = user_id.strip() or DEFAULT_LOCAL_USER_ID
        with closing(self._connect()) as con:
            cur = con.execute(
                "DELETE FROM watchlist_item WHERE user_id = ? AND symbol = ?",
                (uid, sym),
            )
            con.commit()
            return cur.rowcount > 0


_repo: SqliteWatchlistRepository | None = None


def reset_watchlist_repository_singleton() -> None:
    """Clear cached repo (tests / process reload)."""
    global _repo
    _repo = None


def get_watchlist_repository() -> SqliteWatchlistRepository:
    global _repo
    if _repo is None:
        _repo = SqliteWatchlistRepository()
    return _repo
