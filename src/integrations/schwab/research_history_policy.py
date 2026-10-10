from __future__ import annotations

from typing import Any

import pandas as pd

from src.data.schema import normalize_daily_bars

# Research-only session quarantine. Dates belong here only after a preserved raw
# payload audit demonstrates a systematic provider anomaly across unrelated assets.
QUARANTINED_SESSION_DATES = {
    pd.Timestamp("2023-06-05", tz="UTC").date(),
}


def find_invalid_ohlc_rows(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.copy()

    for column in ("open", "high", "low", "close"):
        x[column] = pd.to_numeric(x[column], errors="coerce")

    invalid = (
        (x["low"] > x[["open", "close", "high"]].min(axis=1))
        | (x["high"] < x[["open", "close", "low"]].max(axis=1))
    )
    return x.loc[invalid].copy()


def quarantine_known_bad_sessions(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = frame.copy()
    x["timestamp"] = pd.to_datetime(x["timestamp"], utc=True)

    invalid = find_invalid_ohlc_rows(x)
    if invalid.empty:
        return x, invalid

    invalid_dates = set(invalid["timestamp"].dt.date)
    unknown = invalid_dates - QUARANTINED_SESSION_DATES
    if unknown:
        raise ValueError(
            "Research history contains invalid OHLC outside the approved quarantine: "
            f"{sorted(str(value) for value in unknown)}"
        )

    cleaned = x.loc[
        ~x["timestamp"].dt.date.isin(QUARANTINED_SESSION_DATES)
    ].reset_index(drop=True)
    return cleaned, invalid



def normalize_research_price_history(
    payload: dict[str, Any],
    symbol: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if bool(payload.get("empty", False)):
        raise ValueError(f"Schwab returned an empty price history for {symbol}.")

    candles = payload.get("candles")
    if not isinstance(candles, list) or not candles:
        raise ValueError(f"Schwab payload contains no candles for {symbol}.")

    frame = pd.DataFrame(candles)
    required = {"datetime", "open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            f"Schwab candles for {symbol} are missing fields: {sorted(missing)}"
        )

    frame = frame.rename(columns={"datetime": "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)

    cleaned, quarantined = quarantine_known_bad_sessions(frame)
    normalized = normalize_daily_bars(cleaned, symbol)
    return normalized, quarantined
