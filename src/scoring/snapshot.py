from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.scoring import CONTEXT_FEATURES, SCORING_FEATURES
from src.features.data_source import get_feature_data_source


def build_latest_feature_snapshot(
    *,
    provider: str,
    feature_manifest_path: Path | None = None,
) -> pd.DataFrame:
    source = get_feature_data_source(provider)
    manifest_path = feature_manifest_path or (source.feature_dir / "feature_manifest.csv")
    manifest = pd.read_csv(manifest_path, keep_default_na=False)

    required_manifest_columns = {"symbol", "output_path"}
    missing_manifest = required_manifest_columns - set(manifest.columns)
    if missing_manifest:
        raise ValueError(
            f"Feature manifest missing required columns: {sorted(missing_manifest)}"
        )

    rows: list[pd.Series] = []

    for record in manifest.to_dict(orient="records"):
        symbol = str(record["symbol"])
        frame = pd.read_csv(record["output_path"])
        if frame.empty:
            raise ValueError(f"Feature file is empty for {symbol}: {record['output_path']}")

        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        latest = frame.sort_values("timestamp").iloc[-1].copy()

        missing_features = [
            feature
            for feature in (*SCORING_FEATURES, *CONTEXT_FEATURES)
            if feature not in frame.columns
        ]
        if missing_features:
            raise ValueError(
                f"{symbol} feature file missing contract columns: {missing_features}"
            )

        rows.append(latest)

    if not rows:
        raise ValueError("Feature manifest produced an empty scoring snapshot")

    snapshot = pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)
    return snapshot
