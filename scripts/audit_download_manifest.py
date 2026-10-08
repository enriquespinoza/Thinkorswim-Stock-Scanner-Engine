from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "symbol",
    "rows",
    "eligible",
    "eligibility_reasons",
    "data_hash",
    "output_path",
    "status",
    "error",
    "manifest_hash",
]


def audit_manifest(path: Path, expected_symbols: int | None = None) -> None:
    frame = pd.read_csv(path, keep_default_na=False)

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Manifest is missing required columns: {missing}")

    if frame["symbol"].duplicated().any():
        duplicates = sorted(frame.loc[frame["symbol"].duplicated(), "symbol"].unique())
        raise ValueError(f"Duplicate symbols in manifest: {duplicates}")

    total = len(frame)
    ok = frame["status"].eq("ok")
    failed = ~ok
    eligible = frame["eligible"].astype(str).str.lower().eq("true")
    ineligible = ok & ~eligible
    hashed = frame["data_hash"].astype(str).str.len().eq(64)
    manifest_hashes = frame["manifest_hash"].astype(str)
    unique_manifest_hashes = sorted(set(manifest_hashes[manifest_hashes != ""]))

    print("=" * 80)
    print("MARKET-DATA INGESTION AUDIT")
    print("=" * 80)
    print(f"Manifest: {path}")
    print(f"Symbols: {total}")
    if expected_symbols is not None:
        print(f"Expected symbols: {expected_symbols}")
        print(f"Universe coverage: {total / expected_symbols:.2%}")
    print(f"Successful downloads: {int(ok.sum())}")
    print(f"Failed downloads: {int(failed.sum())}")
    print(f"Eligible after Phase-1 gates: {int(eligible.sum())}")
    print(f"Ineligible after Phase-1 gates: {int(ineligible.sum())}")
    print(f"Successful rows with SHA-256 hash: {int((ok & hashed).sum())}/{int(ok.sum())}")
    print(f"Unique manifest hashes: {len(unique_manifest_hashes)}")

    if unique_manifest_hashes:
        print(f"Manifest SHA-256: {unique_manifest_hashes[0]}")

    if ok.any():
        successful_rows = pd.to_numeric(frame.loc[ok, "rows"], errors="coerce")
        print()
        print("Successful history row counts:")
        print(f"  minimum: {int(successful_rows.min())}")
        print(f"  median:  {successful_rows.median():.0f}")
        print(f"  maximum: {int(successful_rows.max())}")

        short = frame.loc[ok & (pd.to_numeric(frame["rows"], errors="coerce") < 252), ["symbol", "rows"]]
        if not short.empty:
            print()
            print("Successful downloads with fewer than 252 rows:")
            print(short.to_string(index=False))

    if failed.any():
        print()
        print("FAILED DOWNLOADS")
        print(frame.loc[failed, ["symbol", "error"]].to_string(index=False))

    if ineligible.any():
        print()
        print("INELIGIBLE SECURITIES")
        print(
            frame.loc[ineligible, ["symbol", "rows", "eligibility_reasons"]]
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

    if expected_symbols is not None and total != expected_symbols:
        raise SystemExit(
            f"FAIL: manifest contains {total} symbols; expected {expected_symbols}"
        )

    if failed.any():
        raise SystemExit(
            f"REVIEW REQUIRED: {int(failed.sum())} market-data downloads failed"
        )

    if not (ok & hashed).all():
        raise SystemExit("REVIEW REQUIRED: one or more successful downloads lack a valid SHA-256 hash")

    if len(unique_manifest_hashes) != 1:
        raise SystemExit("REVIEW REQUIRED: manifest rows do not share one deterministic manifest hash")

    print()
    print("AUDIT PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a scanner market-data download manifest.")
    parser.add_argument("manifest_csv", type=Path)
    parser.add_argument("--expected-symbols", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    audit_manifest(args.manifest_csv, expected_symbols=args.expected_symbols)
