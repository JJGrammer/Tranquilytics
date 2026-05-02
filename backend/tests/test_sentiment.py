from app.services.sentiment import analyze_headlines


def test_sentiment_defaults_when_no_news() -> None:
    s = analyze_headlines([])
    assert s.headline_count == 0
    assert s.label == "Neutral"
    assert s.probability_bullish_aligned == 0.5


def test_sentiment_positive_headline_raises_prob() -> None:
    items = [{"title": "Stock surges after strong earnings surprise", "publisher": "mock"}]
    s = analyze_headlines(items)
    assert s.headline_count >= 1
    assert s.probability_bullish_aligned >= 0.5
