from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.data_sources import (
    SCHWAB_FEATURE_DIR,
    SCHWAB_MANIFEST_DIR,
    SCHWAB_NORMALIZED_DIR,
    SCHWAB_REFERENCE_NORMALIZED_DIR,
)
from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR


@dataclass(frozen=True)
class FeatureDataSource:
    name: str
    bars_dir: Path
    reference_dir: Path
    feature_dir: Path
    manifest_path: Path


def get_feature_data_source(name: str) -> FeatureDataSource:
    normalized = str(name).strip().lower()

    if normalized == "yahoo":
        return FeatureDataSource(
            name="yahoo",
            bars_dir=RAW_DATA_DIR,
            reference_dir=RAW_DATA_DIR / "references",
            feature_dir=PROCESSED_DATA_DIR / "features",
            manifest_path=RAW_DATA_DIR / "download_manifest.csv",
        )

    if normalized == "schwab":
        return FeatureDataSource(
            name="schwab",
            bars_dir=SCHWAB_NORMALIZED_DIR,
            reference_dir=SCHWAB_REFERENCE_NORMALIZED_DIR,
            feature_dir=SCHWAB_FEATURE_DIR,
            manifest_path=SCHWAB_MANIFEST_DIR / "download_manifest.csv",
        )

    raise ValueError(f"Unsupported feature data source: {name}")
