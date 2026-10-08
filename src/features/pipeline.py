from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from config.features import FEATURE_COLUMNS, PORTFOLIO_REFERENCE_SYMBOLS, SECTOR_BENCHMARKS
from src.features.core import compute_core_features
from src.features.relative import add_benchmark_features


def build_symbol_feature_frame(
    bars: pd.DataFrame,
    *,
    sector: str,
    reference_bars: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    missing_references = [
        symbol
        for symbol in PORTFOLIO_REFERENCE_SYMBOLS
        if symbol not in reference_bars
    ]
    if missing_references:
        raise ValueError(f"Missing portfolio reference data: {missing_references}")

    if sector not in SECTOR_BENCHMARKS:
        raise ValueError(f"No sector benchmark configured for sector: {sector}")

    sector_benchmark = SECTOR_BENCHMARKS[sector]
    if sector_benchmark not in reference_bars:
        raise ValueError(f"Missing sector benchmark data: {sector_benchmark}")

    result = compute_core_features(bars)

    result = add_benchmark_features(
        result,
        reference_bars["SPY"],
        "spy",
        include_excess_returns=True,
        include_beta=True,
    )

    for symbol in ("QQQ", "TLT", "GLD", "SCHD"):
        result = add_benchmark_features(
            result,
            reference_bars[symbol],
            symbol.lower(),
        )

    result = add_benchmark_features(
        result,
        reference_bars[sector_benchmark],
        "sector",
        include_excess_returns=True,
    )

    result["sector"] = sector
    result["sector_benchmark"] = sector_benchmark

    ordered = [
        "timestamp",
        "symbol",
        "sector",
        "sector_benchmark",
        "open",
        "high",
        "low",
        "close",
        "volume",
        *FEATURE_COLUMNS,
    ]
    return result[ordered]
