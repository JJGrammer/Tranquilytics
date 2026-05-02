"""Second headline lane via Google News RSS (distinct from Yahoo-scraped yfinance news)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import httpx

from app.services.cache import SqliteCache

_RSS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TranquilyticsEduBot/1.0; "
        "+https://github.com/) educational research prototype"
    ),
}

_GOOGLE_RSS = "https://news.google.com/rss/search"


def _parse_pub_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError, OverflowError):
        return None


def _publisher_from_google_title(title: str) -> str:
    # Google News titles often end with " - Reuters" etc.
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Google News aggregation"


_alnum_re = re.compile(r"[^a-z0-9]+")


def headline_fingerprint(title: str) -> str:
    t = title.lower().strip()
    if " - " in t:
        t = t.rsplit(" - ", 1)[0].strip()
    return _alnum_re.sub("", t[:90])


def dedupe_news(
    *,
    anchor: list[dict],
    extra: list[dict],
) -> list[dict]:
    """Preserve `anchor` order; append unseen `extra` rows (by fuzzy title fingerprint)."""
    seen = {headline_fingerprint((r.get("title") or "").strip()) for r in anchor}
    out = list(anchor)
    for r in extra:
        fp = headline_fingerprint((r.get("title") or "").strip())
        if not fp:
            continue
        if fp in seen:
            continue
        seen.add(fp)
        out.append(r)
    return out


def fetch_google_news_rss(
    symbol: str,
    *,
    cache: SqliteCache | None = None,
    limit: int = 14,
    ttl_seconds: int = 600,
) -> list[dict]:
    sym = (symbol or "").strip().upper()
    if not sym:
        return []

    def _freeze(rows_in: list[dict]) -> list[dict]:
        frozen: list[dict] = []
        for r in rows_in:
            p = r.get("published")
            frozen.append(
                {
                    **r,
                    "published": p.isoformat()
                    if isinstance(p, datetime)
                    else None,
                }
            )
        return frozen

    def _thaw(raw_rows_m: object) -> list[dict]:
        if not isinstance(raw_rows_m, list):
            return []
        thawed: list[dict] = []
        for r in raw_rows_m:
            if not isinstance(r, dict):
                continue
            p_raw = r.get("published")
            p_out: datetime | None = None
            if isinstance(p_raw, str) and p_raw:
                try:
                    p_clean = p_raw.replace("Z", "+00:00")
                    p_out = datetime.fromisoformat(p_clean)
                except ValueError:
                    p_out = None
            thawed.append({**r, "published": p_out})
        return thawed

    cache_key = f"google_rss:{sym}:n={limit}"
    if cache is not None:
        hit = cache.get(cache_key)
        if hit is not None:
            raw_rows = hit.value.get("items")
            return _thaw(raw_rows)

    q = quote_plus(f"{sym} stock")
    url = f"{_GOOGLE_RSS}?q={q}&hl=en-US&gl=US&ceid=US:en"
    rows: list[dict] = []
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as cli:
            r = cli.get(url, headers=_RSS_HEADERS)
            r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        if cache is not None:
            cache.set(cache_key, {"items": []}, ttl_seconds=ttl_seconds)
        return []

    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        title = (title_el.text if title_el is not None else None) or ""
        title = title.replace("\xa0", " ").strip()
        if not title:
            continue
        link = (link_el.text or "").strip() if link_el is not None else ""
        publisher = _publisher_from_google_title(title)
        published = _parse_pub_date(pub_el.text if pub_el is not None else None)
        rows.append(
            {
                "title": title,
                "publisher": publisher,
                "link": link or None,
                "published": published,
            }
        )
        if len(rows) >= limit:
            break

    if cache is not None:
        cache.set(cache_key, {"items": _freeze(rows)}, ttl_seconds=ttl_seconds)
    return rows
