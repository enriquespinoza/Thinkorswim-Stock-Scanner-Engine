import numpy as np
import pandas as pd

from src.features.core import compute_core_features


def _bars(rows: int = 320) -> pd.DataFrame:
    idx = np.arange(rows, dtype=float)
    close = 100.0 + 0.08 * idx + 2.0 * np.sin(idx / 9.0)
    open_ = close * (1.0 + 0.001 * np.sin(idx / 5.0))
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = 1_000_000.0 + 50_000.0 * np.cos(idx / 11.0)

    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=rows, freq="B", tz="UTC"),
            "symbol": "TEST",
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_return_features_match_direct_pct_change() -> None:
    bars = _bars()
    features = compute_core_features(bars)
    expected = bars["close"].pct_change(20, fill_method=None)
    pd.testing.assert_series_equal(
        features["return_20d"],
        expected,
        check_names=False,
    )


def test_ema_price_relationship_is_algebraically_consistent() -> None:
    features = compute_core_features(_bars())
    valid = features["ema_21"].notna()
    expected = features.loc[valid, "close"] / features.loc[valid, "ema_21"] - 1.0
    np.testing.assert_allclose(features.loc[valid, "price_to_ema_21"], expected)


def test_rsi_is_bounded_when_defined() -> None:
    features = compute_core_features(_bars())
    rsi = features["rsi_14"].dropna()
    assert ((rsi >= 0.0) & (rsi <= 100.0)).all()


def test_volatility_is_nonnegative() -> None:
    features = compute_core_features(_bars())
    assert (features["volatility_20d"].dropna() >= 0.0).all()
    assert (features["downside_volatility_20d"].dropna() >= 0.0).all()


def test_current_drawdown_is_nonpositive() -> None:
    features = compute_core_features(_bars())
    drawdown = features["current_drawdown_60d"].dropna()
    assert (drawdown <= 1e-12).all()


def test_atr_is_positive() -> None:
    features = compute_core_features(_bars())
    assert (features["atr_14"].dropna() > 0.0).all()
