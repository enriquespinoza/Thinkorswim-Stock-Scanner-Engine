from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.scoring import FEATURE_GROUPS, SCORING_FEATURES
from config.weight_research import FORWARD_RETURN_HORIZONS, REBALANCE_FREQUENCY
from src.features.data_source import get_feature_data_source
from src.scoring.normalization import normalize_scoring_snapshot


def _add_forward_returns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("timestamp").reset_index(drop=True).copy()
    close = result["close"].astype(float)

    for horizon in FORWARD_RETURN_HORIZONS:
        result[f"forward_return_{horizon}d"] = close.shift(-horizon) / close - 1.0
        result[f"forward_end_{horizon}d"] = result["timestamp"].shift(-horizon)

    return result


def _group_score_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()

    for group, features in FEATURE_GROUPS.items():
        z_columns = [f"z_{feature}" for feature in features]
        result[f"group_{group}"] = result[z_columns].mean(axis=1, skipna=False)

    return result


def build_historical_scoring_panel(
    *,
    provider: str,
    feature_manifest_path: Path | None = None,
    rebalance_frequency: str = REBALANCE_FREQUENCY,
) -> pd.DataFrame:
    source = get_feature_data_source(provider)
    manifest_path = feature_manifest_path or (source.feature_dir / "feature_manifest.csv")
    manifest = pd.read_csv(manifest_path, keep_default_na=False)

    per_symbol: list[pd.DataFrame] = []

    for record in manifest.to_dict(orient="records"):
        symbol = str(record["symbol"])
        frame = pd.read_csv(record["output_path"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame = _add_forward_returns(frame)
        per_symbol.append(frame)

    history = pd.concat(per_symbol, ignore_index=True)
    history["session_date"] = history["timestamp"].dt.normalize()

    # Pick the last available market session in each requested calendar bucket.
    bucket = history["session_date"].dt.to_period(rebalance_frequency)
    history["rebalance_bucket"] = bucket.astype(str)

    sampled = (
        history.sort_values("timestamp")
        .groupby(["symbol", "rebalance_bucket"], as_index=False)
        .tail(1)
        .drop(columns=["rebalance_bucket"])
    )

    normalized_dates: list[pd.DataFrame] = []
    for _, cross_section in sampled.groupby("session_date", sort=True):
        if len(cross_section) < 50:
            continue

        normalized = normalize_scoring_snapshot(cross_section)
        normalized = _group_score_columns(normalized)
        normalized_dates.append(normalized)

    if not normalized_dates:
        raise ValueError("Historical scoring panel contains no valid cross-sections")

    panel = pd.concat(normalized_dates, ignore_index=True)

    required = [
        "timestamp",
        "session_date",
        "symbol",
        "sector",
        *SCORING_FEATURES,
        *(f"group_{group}" for group in FEATURE_GROUPS),
        *(f"forward_return_{horizon}d" for horizon in FORWARD_RETURN_HORIZONS),
        *(f"forward_end_{horizon}d" for horizon in FORWARD_RETURN_HORIZONS),
        "scoring_complete",
    ]
    return panel[required].sort_values(["session_date", "symbol"]).reset_index(drop=True)
