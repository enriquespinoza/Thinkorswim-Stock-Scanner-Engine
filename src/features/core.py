from __future__ import annotations

import numpy as np
import pandas as pd

from config.features import (
    ANNUALIZATION_FACTOR,
    ATR_WINDOW,
    DRAWDOWN_WINDOW,
    EMA_WINDOWS,
    LIQUIDITY_WINDOW,
    RETURN_WINDOWS,
    RSI_WINDOW,
    VOLATILITY_WINDOWS,
)


def _validate_input(bars: pd.DataFrame) -> None:
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"Feature input is missing columns: {sorted(missing)}")
    if bars.empty:
        raise ValueError("Feature input is empty")
    if bars["symbol"].nunique(dropna=False) != 1:
        raise ValueError("Core feature input must contain exactly one symbol")
    if bars["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps detected in feature input")


def _wilder_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()
    avg_loss = loss.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()

    relative_strength = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def compute_core_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Compute point-in-time-safe daily features for one symbol.

    All rolling calculations use only observations at or before the row's
    timestamp. No forward returns or target labels are produced here.
    """
    _validate_input(bars)

    frame = bars.sort_values("timestamp").reset_index(drop=True).copy()
    close = frame["close"].astype(float)
    volume = frame["volume"].astype(float)
    daily_return = close.pct_change(fill_method=None)

    for window in RETURN_WINDOWS:
        frame[f"return_{window}d"] = close.pct_change(
            periods=window,
            fill_method=None,
        )

    for window in EMA_WINDOWS:
        ema = close.ewm(
            span=window,
            adjust=False,
            min_periods=window,
        ).mean()
        frame[f"ema_{window}"] = ema
        frame[f"price_to_ema_{window}"] = close / ema - 1.0

    frame["ema_9_to_21"] = frame["ema_9"] / frame["ema_21"] - 1.0
    frame["ema_50_to_200"] = frame["ema_50"] / frame["ema_200"] - 1.0
    frame[f"rsi_{RSI_WINDOW}"] = _wilder_rsi(close, RSI_WINDOW)

    for window in VOLATILITY_WINDOWS:
        frame[f"volatility_{window}d"] = (
            daily_return.rolling(window, min_periods=window).std(ddof=1)
            * np.sqrt(ANNUALIZATION_FACTOR)
        )
        downside = daily_return.clip(upper=0.0)
        frame[f"downside_volatility_{window}d"] = (
            downside.pow(2)
            .rolling(window, min_periods=window)
            .mean()
            .pow(0.5)
            * np.sqrt(ANNUALIZATION_FACTOR)
        )

    rolling_high = close.rolling(
        DRAWDOWN_WINDOW,
        min_periods=DRAWDOWN_WINDOW,
    ).max()
    frame[f"current_drawdown_{DRAWDOWN_WINDOW}d"] = close / rolling_high - 1.0

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            frame["high"].astype(float) - frame["low"].astype(float),
            (frame["high"].astype(float) - previous_close).abs(),
            (frame["low"].astype(float) - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(ATR_WINDOW, min_periods=ATR_WINDOW).mean()
    frame[f"atr_{ATR_WINDOW}"] = atr
    frame[f"atr_pct_{ATR_WINDOW}"] = atr / close

    dollar_volume = close * volume
    frame[f"median_dollar_volume_{LIQUIDITY_WINDOW}d"] = dollar_volume.rolling(
        LIQUIDITY_WINDOW,
        min_periods=LIQUIDITY_WINDOW,
    ).median()
    average_volume = volume.rolling(
        LIQUIDITY_WINDOW,
        min_periods=LIQUIDITY_WINDOW,
    ).mean()
    frame[f"relative_volume_{LIQUIDITY_WINDOW}d"] = volume / average_volume

    return frame
