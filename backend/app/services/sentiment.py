"""
Headline sentiment → [0, 1] probability for the synthesizer.

Uses **VADER** (`vaderSentiment`). Supports **multi-feed** pooling (e.g. Yahoo via
yfinance plus Google News RSS) with headline-count-aware aggregation to dilute
single-outlet bias.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer: SentimentIntensityAnalyzer | None = None

LABEL_THRESHOLD = 0.028


def _get_analyzer() -> SentimentIntensityAnalyzer:
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
    c = float(scores["compound"])
    edge = float(scores["pos"]) - float(scores["neg"])
    return float((c + edge) / 2.0)


def _label_from_blended(blended: float) -> str:
    if blended >= LABEL_THRESHOLD:
        return "Bullish"
    if blended <= -LABEL_THRESHOLD:
        return "Bearish"
    return "Neutral"


def _rows_to_snapshot(rows: list[dict], *, feed_breakdown: dict[str, str] | None = None) -> SentimentSnapshot:
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
