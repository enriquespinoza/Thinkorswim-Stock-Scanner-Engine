from __future__ import annotations

import numpy as np
import pandas as pd

from config.scoring import (
    MIN_CROSS_SECTION_SIZE,
    SCORING_FEATURES,
    SIGNAL_DIRECTIONS,
    WINSOR_LOWER_QUANTILE,
    WINSOR_UPPER_QUANTILE,
)


def _winsorized_zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")

    valid = numeric.dropna()
    if len(valid) < MIN_CROSS_SECTION_SIZE:
        return pd.Series(np.nan, index=series.index, dtype=float)

    lower = float(valid.quantile(WINSOR_LOWER_QUANTILE))
    upper = float(valid.quantile(WINSOR_UPPER_QUANTILE))
    clipped = numeric.clip(lower=lower, upper=upper)

    mean = float(clipped.mean(skipna=True))
    std = float(clipped.std(skipna=True, ddof=0))

    if not np.isfinite(std) or std == 0.0:
        return pd.Series(np.nan, index=series.index, dtype=float)

    return (clipped - mean) / std


def normalize_scoring_snapshot(snapshot: pd.DataFrame) -> pd.DataFrame:
    missing = [feature for feature in SCORING_FEATURES if feature not in snapshot.columns]
    if missing:
        raise ValueError(f"Scoring snapshot missing contract features: {missing}")

    result = snapshot.copy()

    for feature in SCORING_FEATURES:
        z = _winsorized_zscore(result[feature])
        result[f"z_{feature}"] = z * SIGNAL_DIRECTIONS[feature]
        result[f"missing_{feature}"] = result[feature].isna()

    result["scoring_missing_count"] = result[
        [f"missing_{feature}" for feature in SCORING_FEATURES]
    ].sum(axis=1)

    result["scoring_complete"] = result["scoring_missing_count"].eq(0)

    forbidden = {"score", "composite_score", "rank", "scanner_rank"}
    accidental = forbidden.intersection(result.columns)
    if accidental:
        raise ValueError(
            f"Phase 3A contract must not produce ranking outputs: {sorted(accidental)}"
        )

    return result
