from __future__ import annotations

import pandas as pd


BAR_COLUMNS = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]


def normalize_daily_bars(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"No market data returned for {symbol}")

    normalized = frame.copy()
    normalized.columns = [str(column).strip().lower().replace(" ", "_") for column in normalized.columns]

    if "date" in normalized.columns and "timestamp" not in normalized.columns:
        normalized = normalized.rename(columns={"date": "timestamp"})

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required.difference(normalized.columns)
    if missing:
        raise ValueError(f"Missing bar columns for {symbol}: {sorted(missing)}")

    normalized = normalized[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
    normalized["symbol"] = symbol.strip().upper()

    for column in ["open", "high", "low", "close", "volume"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
    normalized = normalized.drop_duplicates(subset=["timestamp"], keep="last")
    normalized = normalized.sort_values("timestamp").reset_index(drop=True)

    invalid_ohlc = (
        (normalized["low"] > normalized[["open", "close", "high"]].min(axis=1))
        | (normalized["high"] < normalized[["open", "close", "low"]].max(axis=1))
    )
    if invalid_ohlc.any():
        raise ValueError(f"Invalid OHLC relationships detected for {symbol}")
    if (normalized["volume"] < 0).any():
        raise ValueError(f"Negative volume detected for {symbol}")

    return normalized[BAR_COLUMNS]
