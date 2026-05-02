"""Pick the most recent headline tied to recognizable financial/general news brands."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

# Publisher string hints (lowercase substring match against yfinance "publisher").
_PUBLISHER_SNIPPETS = (
    "reuters",
    "bloomberg",
    "wall street",
    "wsj",
    "financial times",
    "cnbc",
    "yahoo finance",
    "yahoo",  # many rows are branded Yahoo Finance via link
    "marketwatch",
    "associated press",
    "ap news",
    "bbc",
    "cnn",
    "fortune",
    "barron",
    "investopedia",
    "seeking alpha",
    "motley fool",
    "benzinga",
    "investing.com",
)

# Canonical host suffixes (after stripping leading www.).
_HOST_SUFFIXES = (
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "cnbc.com",
    "finance.yahoo.com",
    "yahoo.com",
    "marketwatch.com",
    "apnews.com",
    "cnn.com",
    "bbc.co.uk",
    "bbc.com",
    "investopedia.com",
    "seekingalpha.com",
    "fool.com",
    "benzinga.com",
)


def _norm_host(link: str | None) -> str:
    if not link:
        return ""
    host = urlparse(link).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _is_prioritized_row(item: dict) -> bool:
    pub = (item.get("publisher") or "").lower()
    if any(s in pub for s in _PUBLISHER_SNIPPETS):
        return True
    host = _norm_host(item.get("link"))
    if not host:
        return False
    return any(host == suf or host.endswith("." + suf) for suf in _HOST_SUFFIXES)


def _published_or_min(item: dict) -> datetime:
    t = item.get("published")
    if isinstance(t, datetime):
        return t
    return datetime.min.replace(tzinfo=timezone.utc)


def latest_notable_story(
    news_items: list[dict],
) -> tuple[dict | None, str]:
    """
    Prefer the newest headline that matches a prioritized outlet/domain.
    If none qualify, fall back to the newest headline in the fetched batch.

    Returns (item | None, reason) where reason is 'prioritized_outlet'|'newest_available'|'none'.
    """
    usable = [
        row
        for row in news_items
        if (row.get("title") or "").strip()
    ]
    if not usable:
        return None, "none"

    curated = [row for row in usable if _is_prioritized_row(row)]
    pool = curated if curated else usable
    best = max(pool, key=_published_or_min)
    tag = "prioritized_outlet" if curated else "newest_available"
    return best, tag


def format_featured_citation_source(row: dict, *, tag: str) -> str:
    pub = row.get("publisher") or "unknown"
    title = (row.get("title") or "").strip()
    link = (row.get("link") or "").strip()
    lead = (
        "Most recent from a prioritized mainstream / finance outlet:"
        if tag == "prioritized_outlet"
        else "Most recent headline in fetched batch (no prioritized outlet matched filters):"
    )
    suffix = f" URL: {link}" if link else ""
    return f"{lead} [{pub}] {title}.{suffix}"
