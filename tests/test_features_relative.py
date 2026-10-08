import numpy as np
import pandas as pd

from src.features.core import compute_core_features
from src.features.relative import add_benchmark_features


def _bars(symbol: str, multiplier: float, rows: int = 320) -> pd.DataFrame:
    idx = np.arange(rows, dtype=float)
    base = 100.0 * multiplier
    close = base * (1.0 + 0.0008 * idx + 0.01 * np.sin(idx / 13.0))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=rows, freq="B", tz="UTC"),
            "symbol": symbol,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
        }
    )


def test_identical_return_paths_have_unit_correlation_and_beta() -> None:
    asset = _bars("TEST", 1.0)
    benchmark = _bars("SPY", 3.0)
    features = compute_core_features(asset)
    result = add_benchmark_features(
        features,
        benchmark,
        "spy",
        include_excess_returns=True,
        include_beta=True,
    )
    latest = result.iloc[-1]
    assert abs(latest["corr_spy_60d"] - 1.0) < 1e-10
    assert abs(latest["beta_spy_60d"] - 1.0) < 1e-10
    assert abs(latest["excess_return_spy_20d"]) < 1e-12
    assert abs(latest["excess_return_spy_60d"]) < 1e-12


def test_benchmark_alignment_does_not_forward_fill_missing_dates() -> None:
    asset = _bars("TEST", 1.0)
    benchmark = _bars("SPY", 2.0).drop(index=[300]).reset_index(drop=True)
    features = compute_core_features(asset)
    result = add_benchmark_features(features, benchmark, "spy")
    target_date = asset.loc[300, "timestamp"]
    row = result.loc[result["timestamp"] == target_date].iloc[0]
    assert pd.isna(row["corr_spy_60d"]) or np.isfinite(row["corr_spy_60d"])
