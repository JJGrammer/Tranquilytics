from app.services.sentiment import analyze_multi_sources


def test_multi_source_pooling_weights_when_one_feed_sparse() -> None:
    feeds = {
        "yfinance": [
            {"title": "Huge profit surprise delights investors"},
        ],
        "google_news_rss": [],
    }
    outer = analyze_multi_sources(feeds)
    assert outer.headline_count == 1
    assert "google_news_rss" in outer.feed_breakdown


def test_multi_source_pools_independent_signals() -> None:
    feeds = {
        "yfinance": [{"title": "Company faces severe fraud investigation"}],
        "google_news_rss": [{"title": "Outstanding quarter sends shares soaring"}],
    }
    s = analyze_multi_sources(feeds)
    assert s.headline_count == 2
    assert s.feed_breakdown["yfinance"].startswith("1 headline")

