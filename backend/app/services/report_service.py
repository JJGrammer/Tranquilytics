from __future__ import annotations

"""
Report orchestration (v1).

Primary goal:
- Orchestrate data fetching + feature engineering + ML scoring + advice policy into a
  single, frontend-friendly `ReportResponse`.

Refactor intent:
- This file should remain a coordinator. As the project grows, keep heavy logic in
  dedicated modules (market data, features, ML, policy, sentiment, citations).

Prototype constraints:
- Uses yfinance for OHLC history (fast to iterate).
- Uses a local SQLite cache to reduce external calls and stabilize demos.
"""

from datetime import datetime, timezone

from app.schemas.report import Citation, HorizonAdvice, ReportResponse
from app.services.advice_policy import decide
from app.services.cache import SqliteCache
from app.services.features import compute_technical_features, make_horizon_labels
from app.services.market_data import MarketDataService
from app.services.ml import (
    estimate_expected_return,
    estimate_volatility,
    fit_predict_prob_up,
)


class ReportService:
    def __init__(self) -> None:
        self.cache = SqliteCache()
        self.md = MarketDataService()

    def generate(self, symbol: str, include_citations: bool) -> ReportResponse:
        """
        Generate or serve a cached report.

        The output is explicitly non-imperative to reduce liability: we return "leaning"
        signals + confidence and encourage follow-up research.
        """
        cache_key = f"report:v1:{symbol}:cit={int(include_citations)}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return ReportResponse.model_validate(cached.value)

        info = self.md.try_get_ticker_info(symbol) or {}
        prices, as_of = self.md.get_ohlc_history(symbol, period="1y", interval="1d")
        feat = compute_technical_features(prices)

        # Horizons (trading days): defaults for v1.
        # Later: allow adaptive horizons (e.g., regime change detection).
        short_days = 5
        long_days = 30

        short_label = make_horizon_labels(feat, horizon_days=short_days, buffer_return=0.0)
        long_label = make_horizon_labels(feat, horizon_days=long_days, buffer_return=0.0)

        short_prob = fit_predict_prob_up(feat, short_label)
        long_prob = fit_predict_prob_up(feat, long_label)

        vol = estimate_volatility(feat)
        short_exp = estimate_expected_return(feat, horizon_days=short_days)
        long_exp = estimate_expected_return(feat, horizon_days=long_days)

        short_dec = decide(short_prob, short_exp, vol)
        long_dec = decide(long_prob, long_exp, vol)

        disclaimer = (
            "This report is for educational purposes only and is not financial advice. "
            "Tranquilytics provides analysis signals that may be wrong, incomplete, or delayed."
        )

        summary = self._summarize(
            symbol,
            short_dec.leaning,
            long_dec.leaning,
            short_dec.confidence,
            long_dec.confidence,
        )

        citations: list[Citation] = []
        if include_citations:
            citations = [
                Citation(kind="market_data", source="yfinance (historical OHLC)", as_of=as_of),
                Citation(
                    kind="technical_features",
                    source="Derived features from OHLC (returns, moving averages, RSI, volatility)",
                    as_of=as_of,
                ),
                Citation(
                    kind="model",
                    source="Per-ticker calibrated logistic regression (time-series splits)",
                    as_of=datetime.now(tz=timezone.utc),
                ),
            ]

        resp = ReportResponse(
            symbol=symbol,
            name=info.get("name"),
            currency=info.get("currency"),
            exchange=info.get("exchange"),
            generated_at=datetime.now(tz=timezone.utc),
            as_of=as_of,
            short_term=HorizonAdvice(
                horizon="short",
                window_trading_days=short_days,
                leaning=short_dec.leaning,
                confidence=float(short_dec.confidence),
                expected_return=float(short_exp),
                volatility=float(vol),
            ),
            long_term=HorizonAdvice(
                horizon="long",
                window_trading_days=long_days,
                leaning=long_dec.leaning,
                confidence=float(long_dec.confidence),
                expected_return=float(long_exp),
                volatility=float(vol),
            ),
            summary=summary,
            disclaimer=disclaimer,
            citations=citations,
        )

        # Cache reports briefly (prototype): 15 minutes
        self.cache.set(cache_key, resp.model_dump(mode="json"), ttl_seconds=900)
        return resp

    def _summarize(
        self,
        symbol: str,
        short_leaning: str,
        long_leaning: str,
        short_conf: float,
        long_conf: float,
    ) -> str:
        return (
            f"For {symbol}, the short-term signal is {short_leaning} "
            f"(confidence {short_conf:.0%}). The long-term signal is {long_leaning} "
            f"(confidence {long_conf:.0%}). "
            "Use this as a starting point for research, not a guarantee."
        )

