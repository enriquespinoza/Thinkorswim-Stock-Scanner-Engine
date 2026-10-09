from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config.data_sources import SCHWAB_NORMALIZED_DIR
from config.settings import RAW_DATA_DIR
from src.features.io import load_daily_bars


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare frozen Yahoo Phase-1 bars with normalized Schwab bars."
    )
    parser.add_argument("universe_csv", type=Path)
    parser.add_argument("--price-tolerance-bps", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = pd.read_csv(args.universe_csv)

    rows = []

    for symbol in universe["symbol"].astype(str):
        yahoo_path = RAW_DATA_DIR / f"{symbol}_1d.csv"
        schwab_path = SCHWAB_NORMALIZED_DIR / f"{symbol}_1d.csv"

        if not yahoo_path.exists() or not schwab_path.exists():
            rows.append(
                {
                    "symbol": symbol,
                    "overlap_rows": 0,
                    "latest_date_match": False,
                    "max_close_diff_bps": np.nan,
                    "median_close_diff_bps": np.nan,
                    "volume_match_rate": np.nan,
                    "status": "missing_source",
                }
            )
            continue

        yahoo = load_daily_bars(yahoo_path, symbol)
        schwab = load_daily_bars(schwab_path, symbol)

        merged = yahoo.merge(
            schwab,
            on=["timestamp", "symbol"],
            suffixes=("_yahoo", "_schwab"),
            how="inner",
        )

        if merged.empty:
            rows.append(
                {
                    "symbol": symbol,
                    "overlap_rows": 0,
                    "latest_date_match": False,
                    "max_close_diff_bps": np.nan,
                    "median_close_diff_bps": np.nan,
                    "volume_match_rate": np.nan,
                    "status": "no_overlap",
                }
            )
            continue

        close_diff_bps = (
            (merged["close_schwab"] / merged["close_yahoo"] - 1.0).abs() * 10_000.0
        )
        volume_match = np.isclose(
            merged["volume_schwab"].astype(float),
            merged["volume_yahoo"].astype(float),
            rtol=0.0,
            atol=0.0,
        )

        latest_date_match = (
            yahoo["timestamp"].max() == schwab["timestamp"].max()
        )

        status = (
            "ok"
            if float(close_diff_bps.max()) <= args.price_tolerance_bps
            else "review"
        )

        rows.append(
            {
                "symbol": symbol,
                "overlap_rows": len(merged),
                "latest_date_match": latest_date_match,
                "max_close_diff_bps": float(close_diff_bps.max()),
                "median_close_diff_bps": float(close_diff_bps.median()),
                "volume_match_rate": float(volume_match.mean()),
                "status": status,
            }
        )

    report = pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)

    print("=" * 88)
    print("CROSS-PROVIDER MARKET-DATA AUDIT")
    print("=" * 88)
    print(f"Symbols: {len(report)}")
    print(f"OK: {(report['status'] == 'ok').sum()}")
    print(f"Review: {(report['status'] == 'review').sum()}")
    print(f"Missing/no overlap: {(~report['status'].isin(['ok','review'])).sum()}")

    comparable = report.loc[report["status"].isin(["ok", "review"])]
    if not comparable.empty:
        print(f"Median symbol max close diff (bps): {comparable['max_close_diff_bps'].median():.4f}")
        print(f"Worst close diff (bps): {comparable['max_close_diff_bps'].max():.4f}")
        print(f"Median volume exact-match rate: {comparable['volume_match_rate'].median():.2%}")

    review = report.loc[report["status"] != "ok"]
    if not review.empty:
        print()
        print("SYMBOLS REQUIRING REVIEW")
        print(review.to_string(index=False))

    output = Path("reports/validation/cross_provider_market_data_audit.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(output, index=False)
    print()
    print(f"Saved -> {output}")


if __name__ == "__main__":
    main()
