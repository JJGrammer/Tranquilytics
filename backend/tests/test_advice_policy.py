import pytest

from app.services import advice_policy as ap
from app.services.advice_policy import decide


def test_policy_neutral_when_uncertain() -> None:
    d = decide(prob_up=0.52, expected_return=0.002, volatility=0.03)
    assert d.tone == ap.NEUTRAL


def test_policy_safer_buy_when_strong_signal() -> None:
    d = decide(prob_up=0.8, expected_return=0.08, volatility=0.02)
    assert d.tone == ap.SAFE_BUY


def test_policy_buy_moderate() -> None:
    d = decide(prob_up=0.62, expected_return=0.02, volatility=0.02)
    assert d.tone == ap.BUY


def test_policy_sell_soon_when_weak() -> None:
    d = decide(prob_up=0.18, expected_return=-0.08, volatility=0.02)
    assert d.tone == ap.SELL_SOON


@pytest.mark.parametrize(
    "prob,exp", [(0.35, -0.04), (0.40, -0.03)]
)
def test_policy_sell_moderate(prob: float, exp: float) -> None:
    d = decide(prob_up=prob, expected_return=exp, volatility=0.025)
    assert d.tone == ap.SELL
