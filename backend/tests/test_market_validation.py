from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.services.market_data import (
    MarketDataService,
    _recent_ohlc_supports_symbol,
    quote_type_blocks_screen,
)


def test_quote_type_blocks_mutual_fund() -> None:
    assert quote_type_blocks_screen({"quoteType": "MUTUALFUND"}) is True


def test_quote_type_allows_equity() -> None:
    assert quote_type_blocks_screen({"quoteType": "EQUITY"}) is False


def test_quote_type_missing_ok() -> None:
    assert quote_type_blocks_screen({}) is False
    assert quote_type_blocks_screen(None) is False


def _recent_business_days(n: int) -> pd.DatetimeIndex:
    """Last `n` business days ending at or before now (weekend-safe)."""
    ref = pd.Timestamp.now(tz="UTC")
    span = pd.bdate_range(end=ref, periods=n + 15, tz="UTC")
    return span[-n:]


def test_recent_ohlc_requires_rows_and_close() -> None:
    t = MagicMock()
    t.history.return_value = pd.DataFrame()
    assert _recent_ohlc_supports_symbol(t) is False

    idx = _recent_business_days(5)
    t.history.return_value = pd.DataFrame(
        {"Close": [10.0, 10.5, 11.0, 10.8, 11.2], "Volume": [1e6, 1e6, 0, 1e6, 1e6]},
        index=idx,
    )
    assert _recent_ohlc_supports_symbol(t, max_age_days=60) is True


def test_recent_ohlc_rejects_all_zero_volume() -> None:
    t = MagicMock()
    idx = _recent_business_days(5)
    t.history.return_value = pd.DataFrame(
        {"Close": [10.0, 10.5, 11.0, 10.8, 11.2], "Volume": [0, 0, 0, 0, 0]},
        index=idx,
    )
    assert _recent_ohlc_supports_symbol(t, max_age_days=60) is False


def _good_history_df() -> pd.DataFrame:
    idx = _recent_business_days(8)
    return pd.DataFrame(
        {"Close": [10.0, 10.5, 11.0, 10.8, 11.2, 11.0, 11.1, 11.3], "Volume": [1e6] * 8},
        index=idx,
    )


def test_try_get_ticker_info_history_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTicker:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        fast_info: dict = {}

        @property
        def info(self) -> dict:
            return {"quoteType": "EQUITY", "shortName": "Test Co"}

        def history(self, **_kwargs: object) -> pd.DataFrame:
            return _good_history_df()

    monkeypatch.setattr("app.services.market_data.yf.Ticker", FakeTicker)
    out = MarketDataService().try_get_ticker_info("BK")
    assert out is not None
    assert out["symbol"] == "BK"
    assert out.get("name") == "Test Co"


def test_try_get_ticker_info_accepts_history_when_metadata_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sparse .info (no name/exchange/currency) but valid OHLC still validates."""

    class FakeTicker:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        fast_info: dict = {}

        @property
        def info(self) -> dict:
            return {"quoteType": "EQUITY"}

        def history(self, **_kwargs: object) -> pd.DataFrame:
            return _good_history_df()

    monkeypatch.setattr("app.services.market_data.yf.Ticker", FakeTicker)
    out = MarketDataService().try_get_ticker_info("BK")
    assert out is not None
    assert out["symbol"] == "BK"


def test_try_get_ticker_info_blocks_quote_type_before_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTicker:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        fast_info: dict = {}

        @property
        def info(self) -> dict:
            return {"quoteType": "MUTUALFUND"}

        def history(self, **_kwargs: object) -> pd.DataFrame:
            return _good_history_df()

    monkeypatch.setattr("app.services.market_data.yf.Ticker", FakeTicker)
    assert MarketDataService().try_get_ticker_info("XXX") is None


def test_try_get_company_blurb_truncates_long_business_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTicker:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        @property
        def info(self) -> dict:
            return {"longBusinessSummary": "  We make phones.\n" + ("word " * 120)}

    monkeypatch.setattr("app.services.market_data.yf.Ticker", FakeTicker)
    out = MarketDataService().try_get_company_blurb("ZZZ")
    assert out is not None
    assert "We make phones" in out
    assert len(out) <= 321


def test_try_get_company_blurb_swallows_yahoo_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from yfinance.exceptions import YFRateLimitError

    class FakeTicker:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        @property
        def info(self) -> dict:
            raise YFRateLimitError()

    monkeypatch.setattr("app.services.market_data.yf.Ticker", FakeTicker)
    assert MarketDataService().try_get_company_blurb("AAPL") is None
