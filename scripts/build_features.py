from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config.features import REFERENCE_SYMBOLS, SECTOR_BENCHMARKS
from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.features.io import load_daily_bars, save_feature_frame
from src.features.pipeline import build_symbol_feature_frame
from src.utils.hashing import stable_dataframe_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase-2 feature files for eligible scanner symbols.")
    parser.add_argument("universe_csv", type=Path)
    parser.add_argument("manifest_csv", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = pd.read_csv(args.universe_csv)
    manifest = pd.read_csv(args.manifest_csv, keep_default_na=False)

    eligible = manifest.loc[
        manifest["status"].eq("ok")
        & manifest["eligible"].astype(str).str.lower().eq("true"),
        "symbol",
    ].astype(str)

    reference_dir = RAW_DATA_DIR / "references"
    reference_bars = {
        symbol: load_daily_bars(reference_dir / f"{symbol}_1d.csv", symbol)
        for symbol in REFERENCE_SYMBOLS
    }

    output_dir = PROCESSED_DATA_DIR / "features"
    rows = []

    universe_by_symbol = universe.set_index("symbol")
    for symbol in sorted(eligible):
        if symbol not in universe_by_symbol.index:
            raise ValueError(f"Eligible symbol missing from universe: {symbol}")

        sector = str(universe_by_symbol.loc[symbol, "sector"])
        if sector not in SECTOR_BENCHMARKS:
            raise ValueError(f"No sector benchmark configured for {symbol}: {sector}")

        bars = load_daily_bars(RAW_DATA_DIR / f"{symbol}_1d.csv", symbol)
        features = build_symbol_feature_frame(
            bars,
            sector=sector,
            reference_bars=reference_bars,
        )

        output = output_dir / f"{symbol}_features.csv"
        save_feature_frame(features, output)
        digest = stable_dataframe_hash(features)

        latest = features.iloc[-1]
        rows.append(
            {
                "symbol": symbol,
                "sector": sector,
                "sector_benchmark": latest["sector_benchmark"],
                "rows": len(features),
                "feature_hash": digest,
                "output_path": str(output),
            }
        )

    feature_manifest = pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)
    manifest_hash = stable_dataframe_hash(feature_manifest)
    feature_manifest["manifest_hash"] = manifest_hash

    output_manifest = output_dir / "feature_manifest.csv"
    feature_manifest.to_csv(output_manifest, index=False)

    print(f"Built feature files: {len(feature_manifest)}")
    print(f"Feature manifest SHA-256: {manifest_hash}")
    print(f"Saved -> {output_manifest}")


if __name__ == "__main__":
    main()
