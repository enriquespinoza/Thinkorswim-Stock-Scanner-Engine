from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "symbol",
    "provider_symbol",
    "provider",
    "provider_version",
    "schema_version",
    "fetched_at_utc",
    "rows",
    "eligible",
    "eligibility_reasons",
    "raw_payload_hash",
    "normalized_data_hash",
    "raw_path",
    "normalized_path",
    "status",
    "error",
    "manifest_hash",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the versioned Schwab market-data ingestion manifest."
    )
    parser.add_argument("manifest_csv", type=Path)
    parser.add_argument("--expected-symbols", type=int, default=503)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.manifest_csv, keep_default_na=False)

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Manifest missing required columns: {missing}")

    duplicate_symbols = frame.loc[frame["symbol"].duplicated(), "symbol"].tolist()
    if duplicate_symbols:
        raise ValueError(f"Duplicate symbols in manifest: {duplicate_symbols}")

    ok = frame["status"].eq("ok")
    failed = ~ok
    eligible = frame["eligible"].astype(str).str.lower().eq("true")
    ineligible = ok & ~eligible

    raw_hashed = frame["raw_payload_hash"].astype(str).str.len().eq(64)
    normalized_hashed = frame["normalized_data_hash"].astype(str).str.len().eq(64)
    manifest_hashes = sorted(
        set(frame.loc[frame["manifest_hash"].ne(""), "manifest_hash"].astype(str))
    )

    print("=" * 88)
    print("SCHWAB MARKET-DATA INGESTION AUDIT")
    print("=" * 88)
    print(f"Symbols: {len(frame)}")
    print(f"Expected symbols: {args.expected_symbols}")
    print(f"Universe coverage: {len(frame) / args.expected_symbols:.2%}")
    print(f"Successful: {int(ok.sum())}")
    print(f"Failed: {int(failed.sum())}")
    print(f"Eligible: {int(eligible.sum())}")
    print(f"Ineligible successful histories: {int(ineligible.sum())}")
    print(f"Successful raw payloads hashed: {int((ok & raw_hashed).sum())}/{int(ok.sum())}")
    print(
        "Successful normalized histories hashed: "
        f"{int((ok & normalized_hashed).sum())}/{int(ok.sum())}"
    )
    print(f"Unique manifest hashes: {len(manifest_hashes)}")
    if manifest_hashes:
        print(f"Manifest SHA-256: {manifest_hashes[0]}")

    if ok.any():
        rows = pd.to_numeric(frame.loc[ok, "rows"], errors="coerce")
        print()
        print("Successful history row counts:")
        print(f"  minimum: {int(rows.min())}")
        print(f"  median:  {rows.median():.0f}")
        print(f"  maximum: {int(rows.max())}")

    if failed.any():
        print()
        print("FAILED SYMBOLS")
        print(
            frame.loc[
                failed,
                ["symbol", "provider_symbol", "error"],
            ].to_string(index=False)
        )

    if ineligible.any():
        print()
        print("INELIGIBLE SYMBOLS")
        print(
            frame.loc[
                ineligible,
                ["symbol", "rows", "eligibility_reasons"],
            ]
            .sort_values(["eligibility_reasons", "symbol"])
            .to_string(index=False)
        )

        print()
        print("Ineligibility reason counts:")
        reasons = (
            frame.loc[ineligible, "eligibility_reasons"]
            .str.split("|")
            .explode()
            .value_counts()
        )
        print(reasons.to_string())

    if len(frame) != args.expected_symbols:
        raise SystemExit(
            f"REVIEW REQUIRED: manifest contains {len(frame)} symbols; "
            f"expected {args.expected_symbols}"
        )

    if not raw_hashed.loc[ok].all():
        raise SystemExit(
            "REVIEW REQUIRED: one or more successful raw payloads lack SHA-256 hashes"
        )

    if not normalized_hashed.loc[ok].all():
        raise SystemExit(
            "REVIEW REQUIRED: one or more successful normalized histories lack SHA-256 hashes"
        )

    if len(manifest_hashes) != 1:
        raise SystemExit(
            "REVIEW REQUIRED: manifest rows do not share one deterministic hash"
        )

    if failed.any():
        raise SystemExit(
            f"REVIEW REQUIRED: {int(failed.sum())} Schwab market-data requests failed"
        )

    print()
    print("SCHWAB INGESTION AUDIT PASSED")


if __name__ == "__main__":
    main()
