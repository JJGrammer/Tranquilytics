"""Classify rolling daily-return volatility into a simple risk bucket for UX."""


def risk_level_from_volatility(daily_vol: float | None) -> str:
    if daily_vol is None:
        return "Moderate"
    if daily_vol < 0.012:
        return "Low"
    if daily_vol < 0.028:
        return "Moderate"
    return "High"
