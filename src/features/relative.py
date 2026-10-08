from __future__ import annotations

import numpy as np
import pandas as pd

from config.features import CORRELATION_WINDOW, RELATIVE_RETURN_WINDOWS


def _close_series(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    required = {"timestamp", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} data is missing columns: {sorted(missing)}")

    out = frame[["timestamp", "close"]].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out = out.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    return out.rename(columns={"close": f"close_{label}"})


def add_benchmark_features(
    features: pd.DataFrame,
    benchmark_bars: pd.DataFrame,
    label: str,
    *,
    include_excess_returns: bool = False,
    include_beta: bool = False,
) -> pd.DataFrame:
    """Attach aligned relative-return/correlation features for one benchmark."""
    result = features.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)

    benchmark = _close_series(benchmark_bars, label)
    result = result.merge(benchmark, on="timestamp", how="left", validate="one_to_one")

    asset_close = result["close"].astype(float)
    benchmark_close = result[f"close_{label}"].astype(float)
    asset_daily = asset_close.pct_change(fill_method=None)
    benchmark_daily = benchmark_close.pct_change(fill_method=None)

    if include_excess_returns:
        for window in RELATIVE_RETURN_WINDOWS:
            asset_return = asset_close.pct_change(window, fill_method=None)
            benchmark_return = benchmark_close.pct_change(window, fill_method=None)
            result[f"excess_return_{label}_{window}d"] = asset_return - benchmark_return

    result[f"corr_{label}_{CORRELATION_WINDOW}d"] = asset_daily.rolling(
        CORRELATION_WINDOW,
        min_periods=CORRELATION_WINDOW,
    ).corr(benchmark_daily)

    if include_beta:
        covariance = asset_daily.rolling(
            CORRELATION_WINDOW,
            min_periods=CORRELATION_WINDOW,
        ).cov(benchmark_daily)
        benchmark_variance = benchmark_daily.rolling(
            CORRELATION_WINDOW,
            min_periods=CORRELATION_WINDOW,
        ).var(ddof=1)
        result[f"beta_{label}_{CORRELATION_WINDOW}d"] = covariance / benchmark_variance.replace(0.0, np.nan)

    return result.drop(columns=[f"close_{label}"])
