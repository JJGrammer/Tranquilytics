"""
Static explanations for confidence and synthesizer logic (mirrors frontend/src/analysisExplanations.ts).

Used for documentation parity; UI text is served from the TypeScript module. Adjust both when
changing advice_policy.py or synthesizer.py.
"""

from __future__ import annotations

CONFIDENCE_SECTIONS: list[dict[str, str]] = [
    {
        "heading": "What the bar shows",
        "content": (
            "The bar is the width of the numeric confidence value returned for the current tone, "
            "after blending technical and headline signals. Clamped to 0–100% for display. "
            "Not a forecast accuracy score."
        ),
    },
    {
        "heading": "Inputs to the policy layer",
        "content": (
            "p = blended probability-up from synthesizer; μ = nudged expected return heuristic; "
            "σ = daily vol. buffer = clamp(σ×0.75, 0.005, 0.030); edge_buffer = buffer × 1.35."
        ),
    },
    {
        "heading": "Tone and confidence (advice_policy.decide)",
        "content": (
            "Safer Buy: p≥0.73 and μ≥edge_buffer. Sell Soon: p≤0.27 and μ≤−edge_buffer. "
            "Buy: p≥0.58 and μ≥buffer (conf=p). Sell: p≤0.42 and μ≤−buffer (conf=1−p). "
            "Else Neutral: conf = 1 − 2|p−0.5|."
        ),
    },
]

SYNTHESIZER_SECTIONS_BASE: list[dict[str, str]] = [
    {
        "heading": "Streams",
        "content": (
            "Technical: logistic regression on features, optional isotonic calibration. "
            "Headlines: VADER on titles, pooled per horizon."
        ),
    },
    {
        "heading": "Blend",
        "content": (
            "p_blend = (w_t×P_tech + w_s×P_sent) / (w_t+w_s). "
            "Short defaults: 56% / 44%; long: 70% / 30% (synthesizer.py)."
        ),
    },
    {
        "heading": "Return nudge",
        "content": "μ = clip(μ_raw + 0.02×mean_compound, −0.25, 0.25).",
    },
]


def get_confidence_explanation_dicts() -> list[dict[str, str]]:
    """Sections describing the confidence meter (policy layer)."""
    return [dict(s) for s in CONFIDENCE_SECTIONS]


def get_synthesizer_explanation_dicts() -> list[dict[str, str]]:
    """Sections describing technical + headline blend."""
    return [dict(s) for s in SYNTHESIZER_SECTIONS_BASE]
