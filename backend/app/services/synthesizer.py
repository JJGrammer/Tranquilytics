"""
Blend technical model output with headline sentiment before the tone policy.

Sentiment input is a single probability in [0, 1] per analysis (0.5 = neutral).
Right now that comes from VADER in `sentiment.py`; the same contract works if you
later plug in a REST API or another library that returns positive/negative strength.
"""

from __future__ import annotations

import numpy as np

# Short horizon: news/social tone tends to matter more; long: price structure weighs more.
WEIGHT_SHORT_TECH = 0.56
WEIGHT_SHORT_SENT = 0.44
WEIGHT_LONG_TECH = 0.70
WEIGHT_LONG_SENT = 0.30


def blend_probability(
    technical_prob: float,
    sentiment_prob: float,
    *,
    weight_technical: float,
    weight_sentiment: float,
) -> float:
    """
    Convex combination of two calibrated probabilities in ``[0, 1]``.

    Weights are clamped to ``[0, 1]``, normalized to sum to 1, then:

        w'_t P_tech + w'_s P_sent

    If both weights sanitize to zero, returns ``technical_prob`` unchanged.
    """
    w_t = max(0.0, min(1.0, weight_technical))
    w_s = max(0.0, min(1.0, weight_sentiment))
    s = w_t + w_s
    if s <= 0:
        return technical_prob
    w_t, w_s = w_t / s, w_s / s
    return float(w_t * technical_prob + w_s * sentiment_prob)


def nudge_expected_return(technical_exp: float, mean_compound: float) -> float:
    """Small sentiment tilt on the heuristic return (keeps magnitudes tame)."""
    return float(np.clip(technical_exp + 0.02 * mean_compound, -0.25, 0.25))
