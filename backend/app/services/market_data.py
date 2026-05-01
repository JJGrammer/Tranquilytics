from __future__ import annotations

"""
Market data providers (v1).

Primary goal:
- Fetch ticker metadata and OHLC history with minimal setup for the prototype.

Provider strategy:
- v1 uses yfinance because it is fast to integrate and requires no API key.
- We keep the public interface small so we can add an official provider (e.g. Alpha Vantage)
  as a fallback without changing downstream code.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class TickerInfo:
    symbol: str
    name: str | None
    exchange: str | None
    currency: str | None


class MarketDataService:
    """
    v1: yfinance-first.

    Notes:
    - yfinance is convenient for prototyping, but not an official exchange API.
    - We keep this as a service so Alpha Vantage (or another provider) can be added later.
    """

    def try_get_ticker_info(self, symbol: str) -> dict | None:
        """
        Best-effort metadata lookup.

        Returns None when we cannot find meaningful fields (heuristic for "invalid").
        """
        try:
            t = yf.Ticker(symbol)
            info = t.fast_info or {}
            name = None
            exchange = info.get("exchange")
            currency = info.get("currency")

            # fall back to slower info() only when needed
            if exchange is None or currency is None:
                full = getattr(t, "info", None) or {}
                exchange = exchange or full.get("exchange")
                currency = currency or full.get("currency")
                name = full.get("shortName") or full.get("longName")

            if exchange is None and currency is None and name is None:
                # heuristic: treat as invalid if we couldn't find anything at all
                return None

            return {"symbol": symbol, "name": name, "exchange": exchange, "currency": currency}
        except Exception:
            return None

    def get_ohlc_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> tuple[pd.DataFrame, datetime | None]:
        """
        Returns (df, as_of) where df has columns:
        Open, High, Low, Close, Volume
        """
        t = yf.Ticker(symbol)
        df = t.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            raise ValueError(f"No price history found for {symbol}")

        df = df.reset_index()
        # yfinance may return Date or Datetime column depending on interval
        if "Date" in df.columns:
            ts = pd.to_datetime(df["Date"]).max()
        else:
            ts = pd.to_datetime(df["Datetime"]).max()

        as_of = ts.to_pydatetime().replace(tzinfo=timezone.utc) if ts is not pd.NaT else None
        return df, as_of

