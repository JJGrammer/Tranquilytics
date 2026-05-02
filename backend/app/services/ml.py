from __future__ import annotations

"""
Minimal ML utilities for v1 (technical-only).

Primary goal:
- Produce a probability-like "confidence" signal for positive forward return over a
  given horizon, using per-ticker training from recent history.

Design intent:
- Keep models lightweight, cheap, and fast to iterate (logistic regression + calibration).
- Prefer time-series-aware evaluation splits to reduce leakage.
- Treat this layer as replaceable: sentiment features and more advanced models can be
  introduced without changing the API contract.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class HorizonModelResult:
    horizon_days: int
    prob_up: float
    expected_return: float
    volatility: float


def _feature_columns() -> list[str]:
    return [
        "ret_1d",
        "ret_5d",
        "ret_10d",
        "ma_ratio_5_20",
        "ma_ratio_10_20",
        "vol_5",
        "vol_10",
        "vol_20",
        "rsi_14",
        "volchg_1d",
    ]


def fit_predict_prob_up(
    feat_df: pd.DataFrame,
    label: pd.Series,
) -> float:
    """
    Train a simple time-series-aware classifier and return prob_up for the latest row.
    """
    cols = _feature_columns()
    X = feat_df[cols].replace([np.inf, -np.inf], np.nan).dropna()
    y = label.loc[X.index]

    # Need enough samples to fit; otherwise fall back to a stable baseline.
    if len(X) < 80 or y.nunique() < 2:
        base_rate = float(y.mean()) if len(y) else 0.5
        return max(0.05, min(0.95, base_rate))

    def make_pipeline() -> Pipeline:
        return Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
            ]
        )

    latest = X.iloc[[-1]]

    # TimeSeriesSplit can yield training folds with a single class; calibration then
    # fails inside a fold. Fall back to a plain pipeline fit on the full window.
    try:
        tscv = TimeSeriesSplit(n_splits=5)
        calibrated = CalibratedClassifierCV(
            make_pipeline(), method="isotonic", cv=tscv
        )
        calibrated.fit(X, y)
        prob_up = float(calibrated.predict_proba(latest)[0, 1])
    except ValueError:
        pipe = make_pipeline()
        pipe.fit(X, y)
        prob_up = float(pipe.predict_proba(latest)[0, 1])

    return max(0.01, min(0.99, prob_up))


def estimate_expected_return(feat_df: pd.DataFrame, horizon_days: int) -> float:
    """
    A lightweight expected-return heuristic for v1:
    uses recent drift scaled by horizon, with clamp.
    """
    r = feat_df["ret_1d"].dropna().tail(20)
    if r.empty:
        return 0.0
    drift = float(r.mean())
    exp = drift * float(horizon_days)
    return float(np.clip(exp, -0.25, 0.25))


def estimate_volatility(feat_df: pd.DataFrame) -> float:
    vol = feat_df["ret_1d"].dropna().tail(20).std()
    return float(vol) if pd.notna(vol) else 0.0

