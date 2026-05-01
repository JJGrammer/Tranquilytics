from app.services.advice_policy import decide


def test_policy_defaults_to_hold_when_uncertain() -> None:
    d = decide(prob_up=0.52, expected_return=0.002, volatility=0.03)
    assert d.leaning == "Hold"


def test_policy_buy_when_high_prob_and_return() -> None:
    d = decide(prob_up=0.8, expected_return=0.05, volatility=0.02)
    assert d.leaning == "Leaning Buy"


def test_policy_sell_when_low_prob_and_negative_return() -> None:
    d = decide(prob_up=0.2, expected_return=-0.05, volatility=0.02)
    assert d.leaning == "Leaning Sell"

