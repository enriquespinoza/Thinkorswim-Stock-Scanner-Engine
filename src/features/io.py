from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.schema import normalize_daily_bars


def load_daily_bars(path: str | Path, symbol: str | None = None) -> pd.DataFrame:
    path = Path(path)
    frame = pd.read_csv(path)
    if symbol is None:
        if "symbol" not in frame.columns:
            raise ValueError(f"Cannot infer symbol from {path}")
        symbols = frame["symbol"].dropna().astype(str).str.upper().unique()
        if len(symbols) != 1:
            raise ValueError(f"Expected exactly one symbol in {path}; found {symbols.tolist()}")
        symbol = symbols[0]

    return normalize_daily_bars(frame, symbol)


def save_feature_frame(frame: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
