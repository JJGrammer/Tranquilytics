from __future__ import annotations

"""
Feature engineering (technical signals) for v1.

Primary goal:
- Convert raw OHLCV history into a consistent, model-friendly feature table.

Design intent:
- Keep features simple and explainable (returns, moving averages, volatility, RSI).
- Favor features that are quick to compute and easy to justify in a "why this rating?"
  breakdown later.
"""

import numpy as np
import pandas as pd


def compute_technical_features(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input is yfinance history with columns: Date/Datetime, Open, High, Low, Close, Volume
    Returns a feature frame indexed by row with a 'close' column and engineered features.
    """
    df = price_df.copy()
    # Normalize date column name
    if "Date" in df.columns:
        df["ts"] = pd.to_datetime(df["Date"])
    else:
        df["ts"] = pd.to_datetime(df["Datetime"])

    df = df.sort_values("ts").reset_index(drop=True)
    df["close"] = pd.to_numeric(df["Close"], errors="coerce")
    df["volume"] = pd.to_numeric(df.get("Volume", 0), errors="coerce").fillna(0)

    df["ret_1d"] = df["close"].pct_change()
    df["ret_5d"] = df["close"].pct_change(5)
    df["ret_10d"] = df["close"].pct_change(10)

    df["ma_5"] = df["close"].rolling(5).mean()
    df["ma_10"] = df["close"].rolling(10).mean()
    df["ma_20"] = df["close"].rolling(20).mean()
    df["ma_ratio_5_20"] = df["ma_5"] / df["ma_20"] - 1.0
    df["ma_ratio_10_20"] = df["ma_10"] / df["ma_20"] - 1.0

    df["vol_5"] = df["ret_1d"].rolling(5).std()
    df["vol_10"] = df["ret_1d"].rolling(10).std()
    df["vol_20"] = df["ret_1d"].rolling(20).std()

    # Simple RSI(14)
    delta = df["close"].diff()
    up = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    roll_up = up.rolling(14).mean()
    roll_down = down.rolling(14).mean()
    rs = roll_up / (roll_down + 1e-12)
    df["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

    # Volume change
    df["volchg_1d"] = df["volume"].pct_change().replace([np.inf, -np.inf], np.nan)

    return df


def make_horizon_labels(df: pd.DataFrame, horizon_days: int, buffer_return: float = 0.0) -> pd.Series:
    """
    Binary label: 1 if forward return over horizon exceeds buffer_return, else 0.
    """
    fwd = df["close"].shift(-horizon_days) / df["close"] - 1.0
    return (fwd > buffer_return).astype(int)

