from __future__ import annotations

"""
Maps model outputs to the five-tier tone labels used in the Tranquilytics UI.
Keeps wording non-imperative (no "buy now"); thresholds are tunable without retraining.
"""

from dataclasses import dataclass


# Matches dashboard copy: strongest conviction at the extremes.
SAFE_BUY = "Safer Buy"
BUY = "Buy"
NEUTRAL = "Neutral"
SELL = "Sell"
SELL_SOON = "Sell Soon"


@dataclass(frozen=True)
class AdviceDecision:
    tone: str
    confidence: float


def decide(prob_up: float, expected_return: float, volatility: float) -> AdviceDecision:
    """Score-first mapping: extremes first, then intermediate buy/sell, else neutral."""
    buffer = max(0.005, min(0.03, volatility * 0.75))
    edge_buffer = buffer * 1.35

    # Strong conviction bullish
    if prob_up >= 0.73 and expected_return >= edge_buffer:
        conf = max(prob_up, 0.5 + expected_return / max(buffer, 1e-6) * 0.05)
        return AdviceDecision(tone=SAFE_BUY, confidence=min(1.0, conf))

    # Strong conviction bearish
    if prob_up <= 0.27 and expected_return <= -edge_buffer:
        conf = max(1.0 - prob_up, 0.5 + (-expected_return) / max(buffer, 1e-6) * 0.05)
        return AdviceDecision(tone=SELL_SOON, confidence=min(1.0, conf))

    if prob_up >= 0.58 and expected_return >= buffer:
        return AdviceDecision(tone=BUY, confidence=prob_up)

    if prob_up <= 0.42 and expected_return <= -buffer:
        return AdviceDecision(tone=SELL, confidence=1.0 - prob_up)

    hold_conf = 1.0 - abs(prob_up - 0.5) * 2.0
    return AdviceDecision(tone=NEUTRAL, confidence=max(0.0, min(1.0, hold_conf)))
