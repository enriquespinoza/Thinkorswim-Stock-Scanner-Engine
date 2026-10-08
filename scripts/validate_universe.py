from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "symbol",
    "provider_symbol",
    "name",
    "sector",
    "industry",
    "source",
]


def validate_universe(path: Path) -> None:
    frame = pd.read_csv(path)

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    duplicates = sorted(frame.loc[frame["symbol"].duplicated(), "symbol"].unique())
    if duplicates:
        raise ValueError(f"Duplicate symbols: {duplicates}")

    if frame["symbol"].isna().any() or frame["provider_symbol"].isna().any():
        raise ValueError("Null symbols detected")

    provider_mappings = frame.loc[
        frame["symbol"] != frame["provider_symbol"],
        ["symbol", "provider_symbol"],
    ]

    sector_counts = frame["sector"].value_counts().sort_index()

    print("=" * 72)
    print("UNIVERSE VALIDATION")
    print("=" * 72)
    print(f"Rows: {len(frame)}")
    print(f"Unique symbols: {frame['symbol'].nunique()}")
    print(f"Duplicate symbols: {len(duplicates)}")
    print(f"Unique sectors: {frame['sector'].nunique()}")
    print()
    print("Provider symbol mappings:")
    print(
        provider_mappings.to_string(index=False)
        if not provider_mappings.empty
        else "None"
    )
    print()
    print("Sector counts:")
    print(sector_counts.to_string())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a saved scanner universe snapshot.")
    parser.add_argument("universe_csv", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    validate_universe(args.universe_csv)
