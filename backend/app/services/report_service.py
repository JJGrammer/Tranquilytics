from __future__ import annotations

"""Orchestrates market data → features → ML → tone policy → API response."""

from datetime import datetime, timezone

import pandas as pd

from app.schemas.preview import HorizonPreview, PreviewResponse
from app.schemas.report import Citation, HorizonAdvice, ReportResponse
from app.services.advice_policy import AdviceDecision, decide
from app.services.cache import SqliteCache
from app.services.features import compute_technical_features, make_horizon_labels
from app.services.market_data import MarketDataService
from app.services.ml import (
    estimate_expected_return,
    estimate_volatility,
    fit_predict_prob_up,
)
from app.services.risk import risk_level_from_volatility


def _horizon_reasoning(
    dec: AdviceDecision,
    *,
    horizon_name: str,
    window_days: int,
    expected_return: float,
    vol_bucket: str,
    rsi_hint: float | None,
) -> str:
    rsi_part = ""
    if rsi_hint is not None and not pd.isna(rsi_hint):
        rsi_part = f" Recent RSI(14) is around {float(rsi_hint):.1f}, which informs momentum context."
    return (
        f"For the {horizon_name} view (~{window_days} trading sessions), modeled signals tilt toward '{dec.tone}' "
        f"with confidence roughly {dec.confidence:.0%}.{rsi_part} "
        f"The model's directional bias estimate is about {expected_return * 100:+.2f}% over that window "
        f"under moderate assumptions; headline risk ({vol_bucket}) reflects recent price swings. "
        "This is a statistical summary, not a recommendation to trade."
    )


class ReportService:
    def __init__(self) -> None:
        self.cache = SqliteCache()
        self.md = MarketDataService()

    def preview(self, symbol: str) -> PreviewResponse:
        """Lightweight tones + risk for dashboard (same compute as report, thinner payload)."""
        info = self.md.try_get_ticker_info(symbol)
        if info is None:
            return PreviewResponse(valid=False, symbol=symbol.upper().strip())

        sym = symbol.upper().strip()
        prices, _as_of = self.md.get_ohlc_history(sym, period="1y", interval="1d")
        feat = compute_technical_features(prices)
        short_days, long_days = 5, 30

        short_label = make_horizon_labels(feat, horizon_days=short_days)
        long_label = make_horizon_labels(feat, horizon_days=long_days)
        short_prob = fit_predict_prob_up(feat, short_label)
        long_prob = fit_predict_prob_up(feat, long_label)

        vol = estimate_volatility(feat)
        short_exp = estimate_expected_return(feat, horizon_days=short_days)
        long_exp = estimate_expected_return(feat, horizon_days=long_days)
        risk = risk_level_from_volatility(vol)

        short_dec = decide(short_prob, short_exp, vol)
        long_dec = decide(long_prob, long_exp, vol)

        return PreviewResponse(
            valid=True,
            symbol=sym,
            name=info.get("name"),
            exchange=info.get("exchange"),
            currency=info.get("currency"),
            risk_level=risk,
            short_term=HorizonPreview(tone=short_dec.tone, confidence=float(short_dec.confidence)),
            long_term=HorizonPreview(tone=long_dec.tone, confidence=float(long_dec.confidence)),
        )

    def generate(self, symbol: str, include_citations: bool) -> ReportResponse:
        sym = symbol.upper().strip()
        cache_key = f"report:v2:{sym}:cit={int(include_citations)}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return ReportResponse.model_validate(cached.value)

        info = self.md.try_get_ticker_info(sym) or {}
        prices, as_of = self.md.get_ohlc_history(sym, period="1y", interval="1d")
        feat = compute_technical_features(prices)

        short_days, long_days = 5, 30
        short_label = make_horizon_labels(feat, horizon_days=short_days)
        long_label = make_horizon_labels(feat, horizon_days=long_days)

        short_prob = fit_predict_prob_up(feat, short_label)
        long_prob = fit_predict_prob_up(feat, long_label)

        vol = estimate_volatility(feat)
        short_exp = estimate_expected_return(feat, horizon_days=short_days)
        long_exp = estimate_expected_return(feat, horizon_days=long_days)

        short_dec = decide(short_prob, short_exp, vol)
        long_dec = decide(long_prob, long_exp, vol)
        risk = risk_level_from_volatility(vol)

        last_row = feat.iloc[-1]
        rsi = last_row.get("rsi_14")

        disclaimer = (
            "This report is for educational purposes only and is not financial advice. "
            "Tranquilytics surfaces modeled signals only; outcomes can differ materially from estimates."
        )

        summary = (
            f"For {sym}, modeled short-term tone is {short_dec.tone} (~{short_dec.confidence:.0%}) and "
            f"long-term tone is {long_dec.tone} (~{long_dec.confidence:.0%}). "
            f"Interpreted volatility risk: {risk}. Use independent judgment before acting."
        )

        citations: list[Citation] = []
        if include_citations:
            citations = [
                Citation(kind="market_data", source="yfinance (historical OHLC)", as_of=as_of),
                Citation(
                    kind="technical_features",
                    source="Derived from OHLC: returns, moving averages, RSI, rolling volatility",
                    as_of=as_of,
                ),
                Citation(
                    kind="model",
                    source="Per-ticker calibrated logistic regression with time-series CV",
                    as_of=datetime.now(tz=timezone.utc),
                ),
            ]

        resp = ReportResponse(
            symbol=sym,
            name=info.get("name"),
            currency=info.get("currency"),
            exchange=info.get("exchange"),
            generated_at=datetime.now(tz=timezone.utc),
            as_of=as_of,
            risk_level=risk,
            short_term=HorizonAdvice(
                horizon="short",
                window_trading_days=short_days,
                tone=short_dec.tone,
                confidence=float(short_dec.confidence),
                reasoning=_horizon_reasoning(
                    short_dec,
                    horizon_name="short-term",
                    window_days=short_days,
                    expected_return=float(short_exp),
                    vol_bucket=risk,
                    rsi_hint=float(rsi) if rsi is not None and pd.notna(rsi) else None,
                ),
                expected_return=float(short_exp),
                volatility=float(vol),
            ),
            long_term=HorizonAdvice(
                horizon="long",
                window_trading_days=long_days,
                tone=long_dec.tone,
                confidence=float(long_dec.confidence),
                reasoning=_horizon_reasoning(
                    long_dec,
                    horizon_name="long-term",
                    window_days=long_days,
                    expected_return=float(long_exp),
                    vol_bucket=risk,
                    rsi_hint=float(rsi) if rsi is not None and pd.notna(rsi) else None,
                ),
                expected_return=float(long_exp),
                volatility=float(vol),
            ),
            summary=summary,
            disclaimer=disclaimer,
            citations=citations,
        )

        self.cache.set(cache_key, resp.model_dump(mode="json"), ttl_seconds=900)
        return resp
