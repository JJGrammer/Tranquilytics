from datetime import datetime, timezone

from app.services.news_curate import latest_notable_story


def test_prioritized_picks_latest_curated_when_present() -> None:
    t_old = datetime(2024, 1, 2, tzinfo=timezone.utc)
    t_new = datetime(2024, 1, 10, tzinfo=timezone.utc)
    items = [
        {
            "title": "Z inc updates guidance",
            "publisher": "Local Blog",
            "link": "",
            "published": t_new,
        },
        {
            "title": "X corp earnings beat views",
            "publisher": "Reuters",
            "link": "https://www.reuters.com/x",
            "published": t_old,
        },
    ]
    picked, tag = latest_notable_story(items)
    assert picked is not None
    assert tag == "prioritized_outlet"
    assert picked["publisher"] == "Reuters"


def test_fallback_when_no_curated_matches() -> None:
    items = [
        {
            "title": "Older",
            "publisher": "Unknown Outlet",
            "link": "",
            "published": datetime(2024, 1, 1, tzinfo=timezone.utc),
        },
        {
            "title": "Newer",
            "publisher": "Niche Trader Forum",
            "link": "",
            "published": datetime(2024, 1, 5, tzinfo=timezone.utc),
        },
    ]
    picked, tag = latest_notable_story(items)
    assert picked is not None and picked["title"] == "Newer"
    assert tag == "newest_available"
