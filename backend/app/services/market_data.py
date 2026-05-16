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
from yfinance.exceptions import YFRateLimitError

from app.services.cache import SqliteCache

# Reject obvious non-single-name screens when Yahoo exposes quoteType.
_BLOCKED_QUOTE_TYPES = frozenset(
    {
        "MUTUALFUND",
        "INDEX",
        "CURRENCY",
        "CRYPTOCURRENCY",
        "OPTION",
        "FUTURE",
        "COMMODITY",
        "DR",
        "ECONOMIC",
        "PORTFOLIO",
        "MONEYMARKET",
    }
)


def quote_type_blocks_screen(info: dict | None) -> bool:
    if not info:
        return False
    qt = info.get("quoteType")
    if not isinstance(qt, str):
        return False
    return qt.strip().upper() in _BLOCKED_QUOTE_TYPES


def _quote_type_dict_for_screen(fast: dict, full: dict) -> dict:
    """
    Prefer quoteType from fast_info so we can screen tickers without calling `.info()`,
    which triggers a separate Yahoo request and is easy to rate-limit (then every
    symbol looks "invalid" to the UI).
    """
    qt = fast.get("quoteType")
    if isinstance(qt, str) and qt.strip():
        return {"quoteType": qt.strip()}
    return full


def _recent_ohlc_supports_symbol(t: yf.Ticker, *, max_age_days: int = 35) -> bool:
    """
    Second-line validation when Yahoo metadata is sparse: require recent daily bars,
    a sane last close, and at least one non-zero volume print in the last few sessions.
    """
    try:
        h = t.history(period="60d", interval="1d", auto_adjust=False)
        if h is None or h.empty or len(h) < 2:
            return False
        closes = h["Close"].dropna()
        if closes.empty:
            return False
        last_close = float(closes.iloc[-1])
        if last_close <= 0 or last_close != last_close:
            return False

        last = pd.Timestamp(h.index[-1])
        if last.tzinfo is None:
            last = last.tz_localize("UTC")
        else:
            last = last.tz_convert("UTC")
        now = pd.Timestamp.now(tz=timezone.utc)
        if (now - last).days > max_age_days:
            return False

        vol = h.get("Volume")
        if vol is not None and len(vol) >= 1:
            tail = vol.tail(8)
            if tail.notna().any() and (tail.fillna(0) > 0).sum() == 0:
                return False

        return True
    except YFRateLimitError:
        raise
    except Exception:
        return False


def _truncate_company_summary(text: str, max_len: int = 320) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


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

    def try_get_ticker_info(
        self,
        symbol: str,
        *,
        include_company_description: bool = False,
    ) -> dict | None:
        """
        Best-effort metadata lookup.

        Returns None when we cannot find meaningful fields (heuristic for "invalid").
        `include_company_description` pulls `longBusinessSummary` (one slower yfinance `.info()` read).
        """
        try:
            t = yf.Ticker(symbol)
            fast = t.fast_info or {}
            name = None
            exchange = fast.get("exchange")
            currency = fast.get("currency")
            description: str | None = None

            needs_full = (
                exchange is None
                or currency is None
                or include_company_description
            )

            full: dict = {}
            if needs_full:
                full = getattr(t, "info", None) or {}
                exchange = exchange or full.get("exchange")
                currency = currency or full.get("currency")
                name = name or full.get("shortName") or full.get("longName")

            metadata_ok = bool(name or exchange or currency)

            if metadata_ok:
                if not full and not needs_full:
                    full = _quote_type_dict_for_screen(fast, {})
                    if not full.get("quoteType"):
                        full = getattr(t, "info", None) or {}
                if quote_type_blocks_screen(_quote_type_dict_for_screen(fast, full)):
                    return None
                if include_company_description:
                    if not full:
                        full = getattr(t, "info", None) or {}
                    raw_summary = full.get("longBusinessSummary")
                    blob = raw_summary.strip() if isinstance(raw_summary, str) else ""
                    description = (
                        _truncate_company_summary(blob) if blob else None
                    )
                return {
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "currency": currency,
                    **({"description": description} if description else {}),
                }

            if not full:
                full = _quote_type_dict_for_screen(fast, {})
                if not full.get("quoteType"):
                    full = getattr(t, "info", None) or {}
            if quote_type_blocks_screen(_quote_type_dict_for_screen(fast, full)):
                return None

            if _recent_ohlc_supports_symbol(t):
                name = name or full.get("shortName") or full.get("longName")
                exchange = exchange or full.get("exchange")
                currency = currency or full.get("currency")
                if include_company_description:
                    raw_summary = full.get("longBusinessSummary")
                    blob = raw_summary.strip() if isinstance(raw_summary, str) else ""
                    description = (
                        _truncate_company_summary(blob) if blob else None
                    )
                return {
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "currency": currency,
                    **({"description": description} if description else {}),
                }

            return None
        except YFRateLimitError:
            raise
        except Exception:
            return None

    def try_get_company_blurb(
        self,
        symbol: str,
        *,
        cache: SqliteCache | None = None,
        ttl_seconds: int = 86_400,
    ) -> str | None:
        """
        Fetch ``longBusinessSummary`` via yfinance ``.info()`` (slower, rate-limit prone).

        Split from ``try_get_ticker_info`` so ticker validation and core preview stay on
        the lighter path; if this call fails or is throttled, return ``None`` without
        treating the symbol as invalid.
        """
        sym = (symbol or "").strip().upper()
        if not sym:
            return None

        cache_key = f"company_blurb:{sym}"
        if cache is not None:
            hit = cache.get(cache_key)
            if hit is not None:
                raw = hit.value.get("blurb")
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
                return None

        try:
            t = yf.Ticker(sym)
            full = getattr(t, "info", None) or {}
            raw_summary = full.get("longBusinessSummary")
            blob = raw_summary.strip() if isinstance(raw_summary, str) else ""
            out = _truncate_company_summary(blob) if blob else None
        except YFRateLimitError:
            return None
        except Exception:
            return None

        if cache is not None:
            cache.set(cache_key, {"blurb": out or ""}, ttl_seconds=ttl_seconds)
        return out

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

    def get_news_items(self, symbol: str, limit: int = 24) -> list[dict]:
        """Recent headlines via yfinance (titles used for VADER sentiment)."""
        try:
            t = yf.Ticker(symbol)
            raw = getattr(t, "news", None) or []
            out: list[dict] = []
            for n in raw[:limit]:
                title = (n.get("title") or "").strip()
                if not title:
                    continue
                pub = n.get("providerPublishTime")
                as_of = (
                    datetime.fromtimestamp(int(pub), tz=timezone.utc)
                    if isinstance(pub, (int, float))
                    else None
                )
                out.append(
                    {
                        "title": title,
                        "publisher": n.get("publisher") or "unknown",
                        "link": n.get("link"),
                        "published": as_of,
                    }
                )
            return out
        except YFRateLimitError:
            raise
        except Exception:
            return []

