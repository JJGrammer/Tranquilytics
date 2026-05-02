import numpy as np

from app.services.synthesizer import (
    WEIGHT_LONG_SENT,
    WEIGHT_LONG_TECH,
    blend_probability,
    nudge_expected_return,
)


def test_blend_probability_weights_sum_normalized() -> None:
    assert np.isclose(
        blend_probability(0.9, 0.1, weight_technical=0.56, weight_sentiment=0.44),
        0.56 * 0.9 + 0.44 * 0.1,
    )


def test_blend_long_horizon_favors_technical() -> None:
    blended = blend_probability(
        0.8,
        0.2,
        weight_technical=WEIGHT_LONG_TECH,
        weight_sentiment=WEIGHT_LONG_SENT,
    )
    assert np.isclose(blended, WEIGHT_LONG_TECH * 0.8 + WEIGHT_LONG_SENT * 0.2)


def test_nudge_expected_return_bounded() -> None:
    adj = nudge_expected_return(0.2, mean_compound=1.0)
    assert adj <= 0.25


def test_nudge_expected_return_moves_with_sentiment() -> None:
    base = nudge_expected_return(0.0, mean_compound=0.5)
    assert base > nudge_expected_return(0.0, mean_compound=-0.5)
