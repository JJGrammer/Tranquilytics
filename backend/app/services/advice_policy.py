from __future__ import annotations

"""
Advice policy mapping (v1).

Primary goal:
- Convert model outputs (probability/confidence + magnitude + volatility) into a
  user-facing "Leaning Buy / Hold / Leaning Sell" label.

Why separate from ML:
- We want to be able to tune thresholds and risk buffers without retraining models.
- It makes behavior auditable for grading and easier to refactor safely.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AdviceDecision:
    leaning: str
    confidence: float


def decide(prob_up: float, expected_return: float, volatility: float) -> AdviceDecision:
    """
    Score-first, decision-second policy.

    - Default to Hold unless both probability and magnitude justify action.
    - Use volatility-adjusted buffers to reduce "overtrading" advice.
    """
    # Volatility-adjusted buffer: higher vol => require stronger edge
    buffer = max(0.005, min(0.03, volatility * 0.75))

    buy_thresh = 0.62
    sell_thresh = 0.38

    if prob_up >= buy_thresh and expected_return >= buffer:
        return AdviceDecision(leaning="Leaning Buy", confidence=prob_up)

    if prob_up <= sell_thresh and expected_return <= -buffer:
        return AdviceDecision(leaning="Leaning Sell", confidence=1.0 - prob_up)

    # Holding confidence is "how strongly we think it's not actionable"
    hold_conf = 1.0 - abs(prob_up - 0.5) * 2.0
    return AdviceDecision(leaning="Hold", confidence=max(0.0, min(1.0, hold_conf)))

