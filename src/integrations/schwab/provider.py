from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.data.market_data import DailyBarProvider
from src.data.schema import normalize_daily_bars
from src.integrations.schwab.market_data_client import SchwabMarketDataClient


@dataclass(frozen=True)
class SchwabHistoryResult:
    symbol: str
    provider_symbol: str
    fetched_at_utc: datetime
    raw_payload: dict[str, Any]
    bars: pd.DataFrame


def normalize_schwab_price_history(
    payload: dict[str, Any],
    symbol: str,
) -> pd.DataFrame:
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
    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"],
        unit="ms",
        utc=True,
    )
    return normalize_daily_bars(frame, symbol)


class SchwabDailyBarProvider(DailyBarProvider):
    def __init__(self, client: SchwabMarketDataClient) -> None:
        self.client = client

    def fetch(
        self,
        provider_symbol: str,
        canonical_symbol: str,
        *,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> SchwabHistoryResult:
        payload = self.client.get_daily_price_history_payload(
            provider_symbol,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )
        bars = normalize_schwab_price_history(payload, canonical_symbol)
        return SchwabHistoryResult(
            symbol=canonical_symbol,
            provider_symbol=provider_symbol,
            fetched_at_utc=datetime.now(timezone.utc),
            raw_payload=payload,
            bars=bars,
        )

    def history(
        self,
        provider_symbol: str,
        canonical_symbol: str,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        del period, interval
        return self.fetch(provider_symbol, canonical_symbol).bars
