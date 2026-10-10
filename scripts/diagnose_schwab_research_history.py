from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from config.data_sources import (
    SCHWAB_RESEARCH_MANIFEST_DIR,
    SCHWAB_RESEARCH_REFERENCE_MANIFEST_DIR,
    SCHWAB_RESEARCH_REFERENCE_RAW_DIR,
)


def _error_family(message: str) -> str:
    text = str(message)
    if "Invalid OHLC relationships" in text:
        return "invalid_ohlc"
    if "HTTP 429" in text:
        return "http_429_rate_limit"
    if "HTTP 5" in text:
        return "http_5xx"
    if "HTTP 4" in text:
        return "http_4xx"
    if "empty price history" in text or "no candles" in text:
        return "empty_history"
    return text.split(":", 1)[0] if ":" in text else text or "unknown"


def _invalid_candles(raw_path: Path) -> pd.DataFrame:
    if not raw_path.exists():
        return pd.DataFrame()

    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    candles = payload.get("candles", [])
    if not candles:
        return pd.DataFrame()

    frame = pd.DataFrame(candles)
    required = {"datetime", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()

    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    invalid = (
        (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        | (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
    )
    result = frame.loc[
        invalid,
        ["datetime", "open", "high", "low", "close", "volume"],
    ].copy()
    if not result.empty:
        result["timestamp"] = pd.to_datetime(result["datetime"], unit="ms", utc=True)
        result = result[
            ["timestamp", "open", "high", "low", "close", "volume"]
        ]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose Phase 3B Schwab deep-history ingestion failures."
    )
    parser.add_argument("--show-invalid-bars", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    universe_path = SCHWAB_RESEARCH_MANIFEST_DIR / "download_manifest.csv"
    reference_path = SCHWAB_RESEARCH_REFERENCE_MANIFEST_DIR / "reference_manifest.csv"

    if universe_path.exists():
        universe = pd.read_csv(universe_path, keep_default_na=False)
        failures = universe.loc[universe["status"] != "ok"].copy()
        families = Counter(_error_family(value) for value in failures["error"])

        print("=" * 88)
        print("SCHWAB RESEARCH UNIVERSE FAILURE AUDIT")
        print("=" * 88)
        print(f"Symbols: {len(universe)}")
        print(f"Successful: {(universe['status'] == 'ok').sum()}")
        print(f"Failed: {len(failures)}")
        print()
        print("Failure families:")
        for family, count in families.most_common():
            print(f"  {family}: {count}")

        if not failures.empty:
            print()
            print("FAILED SYMBOLS")
            print(failures[["symbol", "error"]].to_string(index=False))

            print()
            print("FAILED SYMBOL INVALID-OHLC DATE SUMMARY")
            date_counts: Counter[str] = Counter()
            details: list[dict[str, object]] = []

            for record in failures.to_dict(orient="records"):
                symbol = str(record["symbol"])
                raw_path = Path(str(record["raw_path"]))
                invalid = _invalid_candles(raw_path)

                if invalid.empty:
                    details.append(
                        {
                            "symbol": symbol,
                            "invalid_rows": 0,
                            "invalid_dates": "",
                        }
                    )
                    continue

                dates = sorted(set(invalid["timestamp"].dt.date.astype(str)))
                for value in dates:
                    date_counts[value] += 1

                details.append(
                    {
                        "symbol": symbol,
                        "invalid_rows": len(invalid),
                        "invalid_dates": "|".join(dates),
                    }
                )

            print()
            print("Invalid-date counts across failed symbols:")
            for value, count in date_counts.most_common():
                print(f"  {value}: {count}")

            print()
            print(pd.DataFrame(details).to_string(index=False))

    if reference_path.exists():
        references = pd.read_csv(reference_path, keep_default_na=False)
        failed_refs = references.loc[references["status"] != "ok"]

        print()
        print("=" * 88)
        print("SCHWAB RESEARCH REFERENCE FAILURE AUDIT")
        print("=" * 88)
        print(f"References: {len(references)}")
        print(f"Successful: {(references['status'] == 'ok').sum()}")
        print(f"Failed: {len(failed_refs)}")

        for record in failed_refs.to_dict(orient="records"):
            symbol = str(record["symbol"])
            print()
            print(f"{symbol}: {record['error']}")
            invalid = _invalid_candles(
                SCHWAB_RESEARCH_REFERENCE_RAW_DIR / f"{symbol}.json"
            )
            print(f"Invalid OHLC candles in preserved raw payload: {len(invalid)}")
            if not invalid.empty:
                print(invalid.head(args.show_invalid_bars).to_string(index=False))


if __name__ == "__main__":
    main()
