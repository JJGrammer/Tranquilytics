from __future__ import annotations

"""Orchestrates market data, headline sentiment (VADER), synthesis, tone policy."""

from datetime import datetime, timezone

import pandas as pd

from app.schemas.preview import HorizonPreview, PreviewResponse
from app.schemas.report import (
    Citation,
    HorizonAdvice,
    HorizonSynthesis,
    ReportResponse,
)
from app.services.advice_policy import AdviceDecision, decide
from app.services.cache import SqliteCache
from app.services.features import compute_technical_features, make_horizon_labels
from app.services.google_news_feed import dedupe_news, fetch_google_news_rss, headline_fingerprint
from app.services.market_data import MarketDataService
from app.services.news_curate import format_featured_citation_source, latest_notable_story
from app.services.ml import (
    estimate_expected_return,
    estimate_volatility,
    fit_predict_prob_up,
)
from app.services.risk import risk_level_from_volatility
from app.services.sentiment import SentimentSnapshot, analyze_dual_horizon_sentiment
from app.services.synthesizer import (
    WEIGHT_LONG_SENT,
    WEIGHT_LONG_TECH,
    WEIGHT_SHORT_SENT,
    WEIGHT_SHORT_TECH,
    blend_probability,
    nudge_expected_return,
)


def _unique_headline_detail_rows(a: list[dict], b: list[dict], limit: int = 10) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in a + b:
        fp = headline_fingerprint((row.get("title") or "").strip())
        if not fp or fp in seen:
            continue
        seen.add(fp)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _horizon_reasoning(
    dec: AdviceDecision,
    *,
    horizon_name: str,
    window_days: int,
    expected_return_adjusted: float,
    risk_level: str,
    rsi_hint: float | None,
    sent: SentimentSnapshot,
    syn: HorizonSynthesis,
) -> str:
    rsi_part = ""
    if rsi_hint is not None and not pd.isna(rsi_hint):
        rsi_part = f" RSI(14) is near {float(rsi_hint):.1f}."

    if sent.headline_count == 0:
        sent_part = (
            " Headline sentiment for this horizon had no usable text; that layer defaulted to neutral "
            "and only technical signals informed the synthesizer blend."
        )
    elif horizon_name == "short-term":
        sent_part = (
            f" The short-horizon headline layer scored {sent.headline_count} recent headline(s) "
            f"(about the last ~72 hours, or the newest available if dates were sparse), aggregating to "
            f"{sent.label} (compound ≈ {sent.mean_compound:+.2f}). The synthesizer combined that with "
            f"price dynamics using weights {syn.technical_weight:.0%} technical vs "
            f"{syn.sentiment_weight:.0%} headline sentiment before mapping to tones."
        )
    else:
        sent_part = (
            f" The long-horizon headline layer scores a broader narrative (typically one anchor "
            f"headline for sustained context, with a small pooled fallback when needed); "
            f"{sent.headline_count} title(s) in that layer aggregated to {sent.label} "
            f"(compound ≈ {sent.mean_compound:+.2f}). Blend weights were "
            f"{syn.technical_weight:.0%} technical vs {syn.sentiment_weight:.0%} headline sentiment."
        )

    return (
        f"For the {horizon_name} view (~{window_days} sessions), aggregated signals lean toward '{dec.tone}' "
        f"with confidence roughly {dec.confidence:.0%}.{rsi_part}"
        f" {sent_part}"
        f" The adjusted directional bias heuristic is about {expected_return_adjusted * 100:+.2f}% "
        f"over that window under simplifications. Rolling volatility maps to interpreted risk tier '{risk_level}'. "
        "This is exploratory modeling, not a recommendation to trade."
    )


class ReportService:
    def __init__(self) -> None:
        self.cache = SqliteCache()
        self.md = MarketDataService()

    def preview(self, symbol: str) -> PreviewResponse:
        info = self.md.try_get_ticker_info(
            symbol,
            include_company_description=True,
        )
        if info is None:
            return PreviewResponse(valid=False, symbol=symbol.upper().strip())

        sym = symbol.upper().strip()
        yf_news = self.md.get_news_items(sym)
        rss_news = fetch_google_news_rss(sym, cache=self.cache)
        news_merged = dedupe_news(anchor=yf_news, extra=rss_news)
        sent_short, sent_long, _horizon_diag = analyze_dual_horizon_sentiment(
            news_merged,
            yfinance_raw=yf_news,
            rss_raw=rss_news,
        )

        prices, _as_of = self.md.get_ohlc_history(sym, period="1y", interval="1d")
        feat = compute_technical_features(prices)
        short_days, long_days = 5, 30

        short_label = make_horizon_labels(feat, horizon_days=short_days)
        long_label = make_horizon_labels(feat, horizon_days=long_days)
        tech_s = fit_predict_prob_up(feat, short_label)
        tech_l = fit_predict_prob_up(feat, long_label)

        vol = estimate_volatility(feat)
        raw_s_exp = estimate_expected_return(feat, horizon_days=short_days)
        raw_l_exp = estimate_expected_return(feat, horizon_days=long_days)
        short_exp_adj = nudge_expected_return(raw_s_exp, sent_short.mean_compound)
        long_exp_adj = nudge_expected_return(raw_l_exp, sent_long.mean_compound)

        blended_s = blend_probability(
            tech_s,
            sent_short.probability_bullish_aligned,
            weight_technical=WEIGHT_SHORT_TECH,
            weight_sentiment=WEIGHT_SHORT_SENT,
        )
        blended_l = blend_probability(
            tech_l,
            sent_long.probability_bullish_aligned,
            weight_technical=WEIGHT_LONG_TECH,
            weight_sentiment=WEIGHT_LONG_SENT,
        )

        short_dec = decide(blended_s, short_exp_adj, vol)
        long_dec = decide(blended_l, long_exp_adj, vol)
        risk = risk_level_from_volatility(vol)

        return PreviewResponse(
            valid=True,
            symbol=sym,
            name=info.get("name"),
            description=info.get("description"),
            exchange=info.get("exchange"),
            currency=info.get("currency"),
            risk_level=risk,
            sentiment_label=sent_short.label,
            sentiment_headlines_used=sent_short.headline_count,
            sentiment_label_long=sent_long.label,
            sentiment_headlines_long=sent_long.headline_count,
            short_term=HorizonPreview(tone=short_dec.tone, confidence=float(short_dec.confidence)),
            long_term=HorizonPreview(tone=long_dec.tone, confidence=float(long_dec.confidence)),
        )

    def generate(self, symbol: str, include_citations: bool) -> ReportResponse:
        sym = symbol.upper().strip()
        cache_key = f"report:v6:{sym}:cit={int(include_citations)}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return ReportResponse.model_validate(cached.value)

        info = self.md.try_get_ticker_info(sym) or {}
        yf_news = self.md.get_news_items(sym)
        rss_news = fetch_google_news_rss(sym, cache=self.cache)
        news_merged = dedupe_news(anchor=yf_news, extra=rss_news)
        sent_short, sent_long, horizon_diag = analyze_dual_horizon_sentiment(
            news_merged,
            yfinance_raw=yf_news,
            rss_raw=rss_news,
        )

        prices, as_of = self.md.get_ohlc_history(sym, period="1y", interval="1d")
        feat = compute_technical_features(prices)

        short_days, long_days = 5, 30
        short_label = make_horizon_labels(feat, horizon_days=short_days)
        long_label = make_horizon_labels(feat, horizon_days=long_days)

        tech_s = fit_predict_prob_up(feat, short_label)
        tech_l = fit_predict_prob_up(feat, long_label)

        vol = estimate_volatility(feat)
        raw_s_exp = estimate_expected_return(feat, horizon_days=short_days)
        raw_l_exp = estimate_expected_return(feat, horizon_days=long_days)
        short_exp_adj = nudge_expected_return(raw_s_exp, sent_short.mean_compound)
        long_exp_adj = nudge_expected_return(raw_l_exp, sent_long.mean_compound)

        blended_s = blend_probability(
            tech_s,
            sent_short.probability_bullish_aligned,
            weight_technical=WEIGHT_SHORT_TECH,
            weight_sentiment=WEIGHT_SHORT_SENT,
        )
        blended_l = blend_probability(
            tech_l,
            sent_long.probability_bullish_aligned,
            weight_technical=WEIGHT_LONG_TECH,
            weight_sentiment=WEIGHT_LONG_SENT,
        )

        short_dec = decide(blended_s, short_exp_adj, vol)
        long_dec = decide(blended_l, long_exp_adj, vol)
        risk = risk_level_from_volatility(vol)

        syn_short = HorizonSynthesis(
            technical_probability=float(tech_s),
            sentiment_probability=float(sent_short.probability_bullish_aligned),
            blended_probability=float(blended_s),
            technical_weight=float(WEIGHT_SHORT_TECH),
            sentiment_weight=float(WEIGHT_SHORT_SENT),
        )
        syn_long = HorizonSynthesis(
            technical_probability=float(tech_l),
            sentiment_probability=float(sent_long.probability_bullish_aligned),
            blended_probability=float(blended_l),
            technical_weight=float(WEIGHT_LONG_TECH),
            sentiment_weight=float(WEIGHT_LONG_SENT),
        )

        last_row = feat.iloc[-1]
        rsi = last_row.get("rsi_14")
        rsi_hint = float(rsi) if rsi is not None and pd.notna(rsi) else None

        disclaimer = (
            "This report is for educational purposes only and is not financial advice. "
            "Headlines and social-style text can be biased, duplicated, or delayed; fused scores can differ substantially from fundamentals."
        )

        headline_note = (
            f"recent layer: {sent_short.headline_count} headline(s) ({sent_short.label}); "
            f"long narrative layer: {sent_long.headline_count} ({sent_long.label})."
            if (sent_short.headline_count or sent_long.headline_count)
            else "No headline text fetched; headline layers defaulted to neutral."
        )
        summary = (
            f"For {sym}, the synthesizer combined technical history with {headline_note} "
            f"Short tone: {short_dec.tone}; long tone: {long_dec.tone}. "
            f"Volatility-adjusted bucket: {risk}. Verify sources and use independent judgment."
        )

        citations: list[Citation] = []
        if include_citations:
            citations.extend(
                [
                    Citation(kind="market_data", source="yfinance (historical OHLC)", as_of=as_of),
                    Citation(
                        kind="technical_features",
                        source="Derived from OHLC: returns, moving averages, RSI, rolling volatility",
                        as_of=as_of,
                    ),
                    Citation(
                        kind="technical_model",
                        source="Calibrated logistic regression on technical features with time-series CV (fallback fits when folds are degenerate)",
                        as_of=datetime.now(tz=timezone.utc),
                    ),
                    Citation(
                        kind="sentiment_model",
                        source=(
                            "VADER on headlines: short horizon uses a recent window (~72h, else newest "
                            "available); long horizon uses one narrative anchor headline (oldest dated "
                            "story when timestamps exist) with a small pooled fallback—sources are "
                            "yfinance ticker news plus Google News RSS, deduped."
                        ),
                        as_of=datetime.now(tz=timezone.utc),
                    ),
                ]
            )

            for fk, fv in horizon_diag.items():
                citations.append(
                    Citation(
                        kind="sentiment_feed_status",
                        source=f"{fk}: {fv}",
                        as_of=datetime.now(tz=timezone.utc),
                    )
                )

            featured, feat_reason = latest_notable_story(news_merged)
            if featured is not None:
                citations.append(
                    Citation(
                        kind="featured_news",
                        source=format_featured_citation_source(
                            featured, tag=feat_reason
                        ),
                        as_of=featured.get("published"),
                    )
                )

            for row in _unique_headline_detail_rows(
                sent_short.details,
                sent_long.details,
                limit=10,
            ):
                src = row.get("feed") or "mixed"
                citations.append(
                    Citation(
                        kind="news_headline",
                        source=(
                            f"[{src}] [{row['publisher']}] {row['title']}"
                            + (
                                f" (compound={row['compound']:+.3f})"
                                if "compound" in row
                                else ""
                            )
                        ),
                        as_of=row.get("published"),
                    )
                )

        resp = ReportResponse(
            symbol=sym,
            name=info.get("name"),
            currency=info.get("currency"),
            exchange=info.get("exchange"),
            generated_at=datetime.now(tz=timezone.utc),
            as_of=as_of,
            risk_level=risk,
            sentiment_label=sent_short.label,
            sentiment_headlines_used=int(sent_short.headline_count),
            sentiment_label_long=sent_long.label,
            sentiment_headlines_long=int(sent_long.headline_count),
            short_term=HorizonAdvice(
                horizon="short",
                window_trading_days=short_days,
                tone=short_dec.tone,
                confidence=float(short_dec.confidence),
                synthesis=syn_short,
                reasoning=_horizon_reasoning(
                    short_dec,
                    horizon_name="short-term",
                    window_days=short_days,
                    expected_return_adjusted=float(short_exp_adj),
                    risk_level=risk,
                    rsi_hint=rsi_hint,
                    sent=sent_short,
                    syn=syn_short,
                ),
                expected_return=float(short_exp_adj),
                volatility=float(vol),
            ),
            long_term=HorizonAdvice(
                horizon="long",
                window_trading_days=long_days,
                tone=long_dec.tone,
                confidence=float(long_dec.confidence),
                synthesis=syn_long,
                reasoning=_horizon_reasoning(
                    long_dec,
                    horizon_name="long-term",
                    window_days=long_days,
                    expected_return_adjusted=float(long_exp_adj),
                    risk_level=risk,
                    rsi_hint=rsi_hint,
                    sent=sent_long,
                    syn=syn_long,
                ),
                expected_return=float(long_exp_adj),
                volatility=float(vol),
            ),
            summary=summary,
            disclaimer=disclaimer,
            citations=citations,
        )

        self.cache.set(cache_key, resp.model_dump(mode="json"), ttl_seconds=900)
        return resp
