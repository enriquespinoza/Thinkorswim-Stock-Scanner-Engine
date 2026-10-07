from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.universe.providers import UniverseProvider
from src.utils.hashing import stable_dataframe_hash


UNIVERSE_COLUMNS = [
    "symbol",
    "provider_symbol",
    "name",
    "sector",
    "industry",
    "source",
]


def build_universe_frame(provider: UniverseProvider) -> pd.DataFrame:
    securities = provider.load()
    if not securities:
        raise ValueError("Universe provider returned no securities")

    frame = pd.DataFrame([security.as_record() for security in securities])
    frame = frame[UNIVERSE_COLUMNS].copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["provider_symbol"] = frame["provider_symbol"].astype(str).str.strip().str.upper()

    if frame["symbol"].duplicated().any():
        duplicates = sorted(frame.loc[frame["symbol"].duplicated(), "symbol"].unique())
        raise ValueError(f"Duplicate universe symbols: {duplicates}")

    return frame.sort_values("symbol").reset_index(drop=True)


def save_universe_snapshot(frame: pd.DataFrame, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return stable_dataframe_hash(frame)
