from __future__ import annotations

"""
Local cache implementation for the prototype.

Primary goal:
- Reduce repeated external market-data calls (rate limiting + speed).
- Make the demo stable even when upstream services are slow/intermittent.

Design intent:
- SQLite keeps the prototype dependency-light and easy to run locally.
- This file is intentionally narrow so we can replace it with Supabase/Postgres-backed
  caching later without rewriting report logic.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CacheEntry:
    key: str
    value: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class SqliteCache:
    def __init__(self, db_path: str = "app/cache.db") -> None:
        self.db_path = str(Path(db_path))
        self._init()

    def _connect(self) -> sqlite3.Connection:
        # WAL improves concurrency for a dev server; safe for local use.
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    def _init(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                  key TEXT PRIMARY KEY,
                  value_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)")

    def get(self, key: str) -> CacheEntry | None:
        now = datetime.now(tz=timezone.utc)
        with self._connect() as con:
            row = con.execute(
                "SELECT key, value_json, created_at, expires_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None

        expires_at = datetime.fromisoformat(row[3])
        if expires_at <= now:
            self.delete(key)
            return None

        return CacheEntry(
            key=row[0],
            value=json.loads(row[1]),
            created_at=datetime.fromisoformat(row[2]),
            expires_at=expires_at,
        )

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> CacheEntry:
        now = datetime.now(tz=timezone.utc)
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO cache(key, value_json, created_at, expires_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value_json=excluded.value_json,
                  created_at=excluded.created_at,
                  expires_at=excluded.expires_at
                """
                ,
                (
                    entry.key,
                    json.dumps(entry.value, ensure_ascii=False),
                    entry.created_at.isoformat(),
                    entry.expires_at.isoformat(),
                ),
            )
        return entry

    def delete(self, key: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM cache WHERE key = ?", (key,))

