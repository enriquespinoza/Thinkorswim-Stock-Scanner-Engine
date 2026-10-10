from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from config.data_sources import (
    DATA_SOURCE_SCHEMA_VERSION,
    SCHWAB_RESEARCH_MANIFEST_DIR,
    SCHWAB_RESEARCH_NORMALIZED_DIR,
    SCHWAB_RESEARCH_PROVIDER_NAME,
    SCHWAB_RESEARCH_PROVIDER_VERSION,
    SCHWAB_RESEARCH_RAW_DIR,
)
from src.data.provider_artifacts import save_normalized_bars, save_raw_json
from src.integrations.schwab.auth import create_schwab_market_data_client, load_schwab_auth_config
from src.integrations.schwab.research_history_policy import normalize_research_price_history
from src.universe.eligibility import EligibilityPolicy, evaluate_basic_eligibility
from src.universe.symbols import to_schwab_symbol
from src.utils.hashing import stable_dataframe_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download isolated deep Schwab history for Phase 3B research."
    )
    parser.add_argument("universe_csv", type=Path)
    parser.add_argument("--lookback-days", type=int, default=2200)
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry only symbols marked failed in the existing research manifest.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = pd.read_csv(args.universe_csv)

    config = load_schwab_auth_config()
    client = create_schwab_market_data_client(config)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.lookback_days)
    policy = EligibilityPolicy()
    rows: list[dict[str, object]] = []

    existing_path = SCHWAB_RESEARCH_MANIFEST_DIR / "download_manifest.csv"
    existing = None
    retry_symbols: set[str] | None = None
    if args.retry_failed and existing_path.exists():
        existing = pd.read_csv(existing_path, keep_default_na=False)
        retry_symbols = set(
            existing.loc[existing["status"] != "ok", "symbol"].astype(str)
        )

    for record in universe.to_dict(orient="records"):
        symbol = str(record["symbol"])
        provider_symbol = to_schwab_symbol(symbol)

        if retry_symbols is not None and symbol not in retry_symbols:
            continue

        raw_path = SCHWAB_RESEARCH_RAW_DIR / f"{symbol}.json"
        normalized_path = SCHWAB_RESEARCH_NORMALIZED_DIR / f"{symbol}_1d.csv"

        try:
            payload = client.get_daily_price_history_payload(
                provider_symbol,
                start_datetime=start,
                end_datetime=end,
            )
            raw_hash = save_raw_json(payload, raw_path)
            bars, quarantined = normalize_research_price_history(payload, symbol)
            normalized_hash = save_normalized_bars(bars, normalized_path)
            eligible, reasons = evaluate_basic_eligibility(bars, policy)

            rows.append(
                {
                    "symbol": symbol,
                    "provider_symbol": provider_symbol,
                    "provider": SCHWAB_RESEARCH_PROVIDER_NAME,
                    "provider_version": SCHWAB_RESEARCH_PROVIDER_VERSION,
                    "schema_version": DATA_SOURCE_SCHEMA_VERSION,
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    "rows": len(bars),
                    "history_request_mode": "bounded_research",
                    "bounded_rows": len(bars) + len(quarantined),
                    "fallback_rows": "",
                    "quarantined_rows": len(quarantined),
                    "quarantined_dates": "|".join(
                        sorted(set(quarantined["timestamp"].dt.date.astype(str)))
                    ) if not quarantined.empty else "",
                    "eligible": eligible,
                    "eligibility_reasons": "|".join(reasons),
                    "raw_payload_hash": raw_hash,
                    "normalized_data_hash": normalized_hash,
                    "raw_path": str(raw_path),
                    "normalized_path": str(normalized_path),
                    "status": "ok",
                    "error": "",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "symbol": symbol,
                    "provider_symbol": provider_symbol,
                    "provider": SCHWAB_RESEARCH_PROVIDER_NAME,
                    "provider_version": SCHWAB_RESEARCH_PROVIDER_VERSION,
                    "schema_version": DATA_SOURCE_SCHEMA_VERSION,
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    "rows": 0,
                    "history_request_mode": "error",
                    "bounded_rows": "",
                    "fallback_rows": "",
                    "quarantined_rows": "",
                    "quarantined_dates": "",
                    "eligible": False,
                    "eligibility_reasons": "market_data_error",
                    "raw_payload_hash": "",
                    "normalized_data_hash": "",
                    "raw_path": str(raw_path),
                    "normalized_path": str(normalized_path),
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    manifest = pd.DataFrame(rows)

    if existing is not None:
        existing = existing.drop(columns=["manifest_hash"], errors="ignore")
        existing = existing.loc[~existing["symbol"].astype(str).isin(retry_symbols)]
        manifest = pd.concat([existing, manifest], ignore_index=True, sort=False)

    manifest = manifest.sort_values("symbol").reset_index(drop=True)
    manifest_hash = stable_dataframe_hash(manifest)
    manifest["manifest_hash"] = manifest_hash

    SCHWAB_RESEARCH_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    output = SCHWAB_RESEARCH_MANIFEST_DIR / "download_manifest.csv"
    manifest.to_csv(output, index=False)

    print(f"Symbols: {len(manifest)}")
    print(f"Successful: {(manifest['status'] == 'ok').sum()}")
    print(f"Failed: {(manifest['status'] != 'ok').sum()}")
    print(f"Eligible: {manifest['eligible'].astype(str).str.lower().eq('true').sum()}")
    successful = manifest.loc[manifest["status"].eq("ok"), "rows"]
    if not successful.empty:
        print(f"Minimum rows: {int(successful.min())}")
        print(f"Median rows: {int(successful.median())}")
        print(f"Maximum rows: {int(successful.max())}")
    print(f"Manifest SHA-256: {manifest_hash}")
    print(f"Saved -> {output}")


if __name__ == "__main__":
    main()
