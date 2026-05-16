"""
Headline sentiment → [0, 1] probability for the synthesizer.

Uses **VADER** (`vaderSentiment`). Supports **multi-feed** pooling (e.g. Yahoo via
yfinance plus Google News RSS) with headline-count-aware aggregation to dilute
single-outlet bias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer: SentimentIntensityAnalyzer | None = None

LABEL_THRESHOLD = 0.028


def _get_analyzer() -> SentimentIntensityAnalyzer:
    """Lazy singleton; loads VADER lexicon files once per process."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


@dataclass
class SentimentSnapshot:
    headline_count: int
    mean_compound: float
    probability_bullish_aligned: float
    label: str
    details: list[dict] = field(default_factory=list)
    # Per-ingest summaries when multiple feeds contribute (empty otherwise).
    feed_breakdown: dict[str, str] = field(default_factory=dict)


def _per_headline_direction(scores: dict) -> float:
    """Blend compound score with (pos − neg) spread into one scalar per headline."""
    c = float(scores["compound"])
    edge = float(scores["pos"]) - float(scores["neg"])
    return float((c + edge) / 2.0)


def _label_from_blended(blended: float) -> str:
    """Map pooled directional scalar to Bullish / Bearish / Neutral using ``LABEL_THRESHOLD``."""
    if blended >= LABEL_THRESHOLD:
        return "Bullish"
    if blended <= -LABEL_THRESHOLD:
        return "Bearish"
    return "Neutral"


def _rows_to_snapshot(rows: list[dict], *, feed_breakdown: dict[str, str] | None = None) -> SentimentSnapshot:
    """Aggregate scored headline rows into mean compounds + mapped bullish probability ``≈ (blend+1)/2``."""
    if not rows:
        return SentimentSnapshot(
            0,
            0.0,
            0.5,
            "Neutral",
            [],
            feed_breakdown=dict(feed_breakdown or {}),
        )

    compounds = [float(r["compound"]) for r in rows]
    directions = [(float(r["compound"]) + (float(r["pos"]) - float(r["neg"]))) / 2.0 for r in rows]

    mean_c = sum(compounds) / len(compounds)
    mean_dir = sum(directions) / len(directions)
    blended = float((mean_c + mean_dir) / 2.0)
    prob = max(0.02, min(0.98, (blended + 1.0) / 2.0))
    label = _label_from_blended(blended)

    return SentimentSnapshot(
        headline_count=len(rows),
        mean_compound=float(mean_c),
        probability_bullish_aligned=float(prob),
        label=label,
        details=rows,
        feed_breakdown=dict(feed_breakdown or {}),
    )


def analyze_headlines(
    news_items: list[dict],
    *,
    feed_tag: str | None = None,
) -> SentimentSnapshot:
    """
    Score each headline in a single feed; tag rows with ``feed_tag`` when provided.
    """
    if not news_items:
        return SentimentSnapshot(0, 0.0, 0.5, "Neutral", [])

    analyzer = _get_analyzer()
    rows: list[dict] = []

    for it in news_items:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        pub = it.get("publisher") or "unknown"
        scores = analyzer.polarity_scores(title)
        rows.append(
            {
                "title": title,
                "publisher": pub,
                "compound": float(scores["compound"]),
                "pos": float(scores["pos"]),
                "neg": float(scores["neg"]),
                "published": it.get("published"),
                "feed": feed_tag,
                "link": it.get("link"),
            }
        )

    return _rows_to_snapshot(rows)


def analyze_multi_sources(feed_lists: dict[str, list[dict]]) -> SentimentSnapshot:
    """
    Pull VADER summaries per logical source, then **pool all scored titles** once so the
    probability reflects the empirical mix (headline-heavy feeds naturally weigh more).
    """
    breakdown: dict[str, str] = {}
    pooled_rows: list[dict] = []

    for fname, lst in feed_lists.items():
        snap = analyze_headlines(lst, feed_tag=fname)
        if snap.headline_count == 0:
            breakdown[fname] = "No usable headlines returned for this ticker right now."
            continue
        breakdown[fname] = (
            f"{snap.headline_count} headline(s); local tilt={snap.label} "
            f"(avg compound={snap.mean_compound:+.3f})"
        )
        pooled_rows.extend(snap.details)

    return _rows_to_snapshot(pooled_rows, feed_breakdown=breakdown)


SHORT_RECENCY_HOURS = 72
_MIN_SHORT_HEADLINES = 2
_SHORT_FALLBACK_NEWEST = 8
_LONG_FALLBACK_POOL = 10


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _usable_titles(items: list[dict]) -> list[dict]:
    return [it for it in items if (it.get("title") or "").strip()]


def _sort_newest(items: list[dict]) -> list[dict]:
    def key(it: dict) -> datetime:
        p = it.get("published")
        if isinstance(p, datetime):
            return _aware(p)
        return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(items, key=key, reverse=True)


def _sort_oldest(items: list[dict]) -> list[dict]:
    def key(it: dict) -> datetime:
        p = it.get("published")
        if isinstance(p, datetime):
            return _aware(p)
        return datetime.max.replace(tzinfo=timezone.utc)

    return sorted(items, key=key)


def headlines_for_short_horizon(
    merged: list[dict],
    *,
    now: datetime | None = None,
) -> list[dict]:
    """Recent headlines (~72h) for short-term tone; fall back to newest titles if sparse."""
    now = now or datetime.now(tz=timezone.utc)
    usable = _usable_titles(merged)
    if not usable:
        return []

    cutoff = now - timedelta(hours=SHORT_RECENCY_HOURS)
    dated_recent: list[dict] = []
    undated: list[dict] = []
    for it in usable:
        p = it.get("published")
        if isinstance(p, datetime):
            if _aware(p) >= cutoff:
                dated_recent.append(it)
        else:
            undated.append(it)

    if len(dated_recent) >= _MIN_SHORT_HEADLINES:
        return _sort_newest(dated_recent)

    pool = _sort_newest(dated_recent + undated)
    return pool[:_SHORT_FALLBACK_NEWEST] if pool else usable[:_SHORT_FALLBACK_NEWEST]


def pick_long_horizon_headline(merged: list[dict]) -> dict | None:
    """
    One representative "narrative" headline for the long-horizon layer: prefer the
    oldest dated story in the batch (background / sustained story). If dates are
    missing, use the longest title as a coarse stand-in for an overview piece.
    """
    usable = _usable_titles(merged)
    if not usable:
        return None
    dated = [it for it in usable if isinstance(it.get("published"), datetime)]
    if dated:
        return _sort_oldest(dated)[0]
    return max(usable, key=lambda x: len((x.get("title") or "").strip()))


def analyze_dual_horizon_sentiment(
    merged: list[dict],
    *,
    yfinance_raw: list[dict],
    rss_raw: list[dict],
    now: datetime | None = None,
) -> tuple[SentimentSnapshot, SentimentSnapshot, dict[str, str]]:
    """
    Short horizon: VADER on a **recent** headline subset.
    Long horizon: VADER on **one** representative narrative title, with a small
    pooled fallback if that would otherwise be empty.
    """
    now = now or datetime.now(tz=timezone.utc)
    y_n = len(_usable_titles(yfinance_raw))
    r_n = len(_usable_titles(rss_raw))
    u_n = len(_usable_titles(merged))

    short_items = headlines_for_short_horizon(merged, now=now)
    snap_short = analyze_headlines(short_items)

    long_pick = pick_long_horizon_headline(merged)
    if long_pick:
        snap_long = analyze_headlines([long_pick])
    else:
        snap_long = SentimentSnapshot(0, 0.0, 0.5, "Neutral", [])

    if snap_long.headline_count == 0 and merged:
        pool = _usable_titles(merged)[:_LONG_FALLBACK_POOL]
        snap_long = analyze_headlines(pool)

    narr_title = (long_pick.get("title") or "").strip() if long_pick else ""
    if len(narr_title) > 140:
        narr_title = narr_title[:139] + "…"

    breakdown: dict[str, str] = {
        "ingest_yahoo": (
            f"{y_n} usable headline(s) in yfinance batch."
            if y_n
            else "No Yahoo ticker headlines in this fetch (common); other lanes may still contribute."
        ),
        "ingest_google_rss": f"{r_n} usable headline(s) in Google News RSS batch.",
        "deduped_unique": f"{u_n} unique headline(s) after cross-source dedupe.",
        "short_layer": (
            f"{snap_short.headline_count} recent headline(s) scored (~{SHORT_RECENCY_HOURS}h or newest-fallback); "
            f"tilt={snap_short.label} (compound={snap_short.mean_compound:+.3f})"
            if snap_short.headline_count
            else "No headlines available for the short/recent layer; neutral."
        ),
        "long_layer": (
            f"Narrative layer scored {snap_long.headline_count} headline(s); tilt={snap_long.label} "
            f"(compound={snap_long.mean_compound:+.3f})"
            + (f"; anchor: “{narr_title}”" if narr_title else "")
            if snap_long.headline_count
            else "No headline text for the long narrative layer; neutral."
        ),
    }
    return snap_short, snap_long, breakdown
