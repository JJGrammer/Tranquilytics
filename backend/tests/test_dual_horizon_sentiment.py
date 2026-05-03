from datetime import datetime, timedelta, timezone

from app.services.sentiment import (
    analyze_dual_horizon_sentiment,
    headlines_for_short_horizon,
    pick_long_horizon_headline,
)


def test_short_layer_prefers_recent_dated_items() -> None:
    now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=10)
    merged = [
        {"title": "Old macro story", "published": old, "publisher": "x"},
        {"title": "Fresh earnings beat", "published": now - timedelta(hours=5), "publisher": "y"},
    ]
    short = headlines_for_short_horizon(merged, now=now)
    titles = {x["title"] for x in short}
    assert "Fresh earnings beat" in titles
    assert "Old macro story" not in titles


def test_long_pick_is_oldest_dated() -> None:
    a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    b = datetime(2026, 1, 20, tzinfo=timezone.utc)
    merged = [
        {"title": "Newer noise", "published": b, "publisher": "x"},
        {"title": "Older narrative", "published": a, "publisher": "y"},
    ]
    pick = pick_long_horizon_headline(merged)
    assert pick is not None
    assert pick["title"] == "Older narrative"


def test_dual_horizon_uses_rss_when_yahoo_empty() -> None:
    yf: list[dict] = []
    rss = [{"title": "RSS only headline about stock rally", "publisher": "Reuters", "published": None}]
    merged = list(rss)
    s_short, s_long, diag = analyze_dual_horizon_sentiment(
        merged,
        yfinance_raw=yf,
        rss_raw=rss,
        now=datetime.now(tz=timezone.utc),
    )
    assert "No Yahoo ticker headlines" in diag["ingest_yahoo"]
    assert s_short.headline_count >= 1
    assert s_long.headline_count >= 1
