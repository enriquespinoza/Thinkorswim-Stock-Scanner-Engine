from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config.settings import DEFAULT_INTERVAL, DEFAULT_LOOKBACK_PERIOD, RAW_DATA_DIR
from src.data.market_data import YFinanceDailyBarProvider
from src.data.pipeline import download_universe_market_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download normalized daily bars for a saved universe snapshot.")
    parser.add_argument("universe_csv", type=Path)
    parser.add_argument("--period", default=DEFAULT_LOOKBACK_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = pd.read_csv(args.universe_csv)
    provider = YFinanceDailyBarProvider()
    manifest = download_universe_market_data(
        universe=universe,
        provider=provider,
        output_dir=RAW_DATA_DIR,
        period=args.period,
        interval=args.interval,
    )
    manifest_path = RAW_DATA_DIR / "download_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    print(manifest.to_string(index=False))
    print(f"Saved manifest -> {manifest_path}")


if __name__ == "__main__":
    main()
