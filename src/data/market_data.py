from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
from src.data.schema import normalize_daily_bars
from src.utils.hashing import stable_dataframe_hash


class DailyBarProvider(ABC):
    @abstractmethod
    def history(
        self,
        provider_symbol: str,
        canonical_symbol: str,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        raise NotImplementedError


class YFinanceDailyBarProvider(DailyBarProvider):
    def history(
        self,
        provider_symbol: str,
        canonical_symbol: str,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        import yfinance as yf

        raw = yf.download(
            provider_symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw = raw.reset_index()
        return normalize_daily_bars(raw, canonical_symbol)


class StaticDailyBarProvider(DailyBarProvider):
    def __init__(self, data_by_symbol: dict[str, pd.DataFrame]) -> None:
        self.data_by_symbol = data_by_symbol

    def history(
        self,
        provider_symbol: str,
        canonical_symbol: str,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        del provider_symbol, period, interval
        return normalize_daily_bars(self.data_by_symbol[canonical_symbol].copy(), canonical_symbol)


def save_daily_bars(frame: pd.DataFrame, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return stable_dataframe_hash(frame)
