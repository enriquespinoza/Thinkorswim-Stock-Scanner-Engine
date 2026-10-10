from __future__ import annotations

import numpy as np
import pandas as pd

from config.alpha import (
    ALPHA_CONTEXT_FEATURES,
    ALPHA_SPEC_VERSION,
    PRIMARY_ALPHA_SIGNAL,
)
from config.scoring import (
    MIN_CROSS_SECTION_SIZE,
    WINSOR_LOWER_QUANTILE,
    WINSOR_UPPER_QUANTILE,
)


_REQUIRED_COLUMNS = {
    "timestamp",
    "symbol",
    "close",
    "return_20d",
    "return_252d",
    *ALPHA_CONTEXT_FEATURES,
}


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


def compute_momentum_252d_ex_20d(frame: pd.DataFrame) -> pd.Series:
    return (
        (1.0 + pd.to_numeric(frame["return_252d"], errors="coerce"))
        / (1.0 + pd.to_numeric(frame["return_20d"], errors="coerce"))
        - 1.0
    )


def score_alpha_snapshot(snapshot: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(_REQUIRED_COLUMNS.difference(snapshot.columns))
    if missing:
        raise ValueError(f"Alpha snapshot missing required columns: {missing}")

    result = snapshot.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    result[PRIMARY_ALPHA_SIGNAL] = compute_momentum_252d_ex_20d(result)
    result["alpha_score"] = _winsorized_zscore(result[PRIMARY_ALPHA_SIGNAL])
    result["alpha_complete"] = result["alpha_score"].notna()

    result["alpha_rank"] = np.nan
    result["alpha_percentile"] = np.nan

    eligible = result.loc[result["alpha_complete"]].copy()
    eligible = eligible.sort_values(
        ["alpha_score", "symbol"],
        ascending=[False, True],
        kind="stable",
    )
    ranks = pd.Series(
        np.arange(1, len(eligible) + 1, dtype=float),
        index=eligible.index,
    )
    result.loc[eligible.index, "alpha_rank"] = ranks

    if len(eligible) == 1:
        result.loc[eligible.index, "alpha_percentile"] = 100.0
    elif len(eligible) > 1:
        result.loc[eligible.index, "alpha_percentile"] = (
            100.0 * (len(eligible) - ranks) / (len(eligible) - 1)
        )

    result["alpha_spec_version"] = ALPHA_SPEC_VERSION

    output_columns = [
        "timestamp",
        "symbol",
        "close",
        PRIMARY_ALPHA_SIGNAL,
        *ALPHA_CONTEXT_FEATURES,
        "alpha_score",
        "alpha_rank",
        "alpha_percentile",
        "alpha_complete",
        "alpha_spec_version",
    ]

    return result[output_columns].sort_values(
        ["alpha_complete", "alpha_rank", "symbol"],
        ascending=[False, True, True],
        na_position="last",
    ).reset_index(drop=True)
