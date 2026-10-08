import numpy as np
import pandas as pd

from config.features import FEATURE_COLUMNS, SECTOR_BENCHMARKS
from src.features.pipeline import build_symbol_feature_frame


def _bars(symbol: str, phase: float = 0.0, rows: int = 320) -> pd.DataFrame:
    idx = np.arange(rows, dtype=float)
    close = 100.0 + 0.06 * idx + 2.0 * np.sin(idx / 11.0 + phase)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=rows, freq="B", tz="UTC"),
            "symbol": symbol,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0 + 1000.0 * idx,
        }
    )


def test_full_feature_contract() -> None:
    references = {
        "SPY": _bars("SPY", 0.1),
        "QQQ": _bars("QQQ", 0.2),
        "TLT": _bars("TLT", 0.3),
        "GLD": _bars("GLD", 0.4),
        "SCHD": _bars("SCHD", 0.5),
        "XLK": _bars("XLK", 0.6),
    }
    result = build_symbol_feature_frame(
        _bars("TEST"),
        sector="Information Technology",
        reference_bars=references,
    )

    assert result["sector_benchmark"].iloc[-1] == SECTOR_BENCHMARKS["Information Technology"]
    assert all(column in result.columns for column in FEATURE_COLUMNS)
    assert len(FEATURE_COLUMNS) == len(set(FEATURE_COLUMNS))


def test_latest_row_is_fully_populated_with_sufficient_history() -> None:
    references = {
        "SPY": _bars("SPY", 0.1),
        "QQQ": _bars("QQQ", 0.2),
        "TLT": _bars("TLT", 0.3),
        "GLD": _bars("GLD", 0.4),
        "SCHD": _bars("SCHD", 0.5),
        "XLK": _bars("XLK", 0.6),
    }
    result = build_symbol_feature_frame(
        _bars("TEST"),
        sector="Information Technology",
        reference_bars=references,
    )
    latest = result.iloc[-1]
    assert latest[list(FEATURE_COLUMNS)].notna().all()
