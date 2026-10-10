from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from config.data_sources import (
    DATA_SOURCE_SCHEMA_VERSION,
    SCHWAB_MANIFEST_DIR,
    SCHWAB_NORMALIZED_DIR,
    SCHWAB_PROVIDER_NAME,
    SCHWAB_PROVIDER_VERSION,
    SCHWAB_RAW_PAYLOAD_DIR,
)
from src.data.provider_artifacts import save_normalized_bars, save_raw_json
from src.integrations.schwab.auth import (
    create_schwab_market_data_client,
    load_schwab_auth_config,
)
from src.integrations.schwab.provider import SchwabDailyBarProvider
from src.integrations.schwab.history_policy import resolve_daily_history
from src.universe.eligibility import EligibilityPolicy, evaluate_basic_eligibility
from src.universe.symbols import to_schwab_symbol
from src.utils.hashing import stable_dataframe_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and preserve Schwab daily market data for a universe snapshot."
    )
    parser.add_argument("universe_csv", type=Path)
    parser.add_argument("--lookback-days", type=int, default=800)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = pd.read_csv(args.universe_csv)

    config = load_schwab_auth_config()
    client = create_schwab_market_data_client(config)
    provider = SchwabDailyBarProvider(client)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.lookback_days)

    rows = []
    policy = EligibilityPolicy()

    for record in universe.to_dict(orient="records"):
        symbol = str(record["symbol"])
        provider_symbol = to_schwab_symbol(symbol)

        raw_path = SCHWAB_RAW_PAYLOAD_DIR / f"{symbol}.json"
        normalized_path = SCHWAB_NORMALIZED_DIR / f"{symbol}_1d.csv"

        try:
            resolution = resolve_daily_history(
                provider,
                provider_symbol=provider_symbol,
                canonical_symbol=symbol,
                start_datetime=start,
                end_datetime=end,
                minimum_rows=policy.min_history_rows,
            )
            result = resolution.selected

            raw_hash = save_raw_json(result.raw_payload, raw_path)
            normalized_hash = save_normalized_bars(result.bars, normalized_path)
            eligible, reasons = evaluate_basic_eligibility(result.bars, policy)

            rows.append(
                {
                    "symbol": symbol,
                    "provider_symbol": provider_symbol,
                    "provider": SCHWAB_PROVIDER_NAME,
                    "provider_version": SCHWAB_PROVIDER_VERSION,
                    "schema_version": DATA_SOURCE_SCHEMA_VERSION,
                    "fetched_at_utc": result.fetched_at_utc.isoformat(),
                    "rows": len(result.bars),
                    "history_request_mode": resolution.request_mode,
                    "bounded_rows": resolution.initial_rows,
                    "fallback_rows": (
                        "" if resolution.fallback_rows is None else resolution.fallback_rows
                    ),
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
                    "provider": SCHWAB_PROVIDER_NAME,
                    "provider_version": SCHWAB_PROVIDER_VERSION,
                    "schema_version": DATA_SOURCE_SCHEMA_VERSION,
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    "rows": 0,
                    "history_request_mode": "error",
                    "bounded_rows": "",
                    "fallback_rows": "",
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

    manifest = pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)
    manifest_hash = stable_dataframe_hash(manifest)
    manifest["manifest_hash"] = manifest_hash

    SCHWAB_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    output = SCHWAB_MANIFEST_DIR / "download_manifest.csv"
    manifest.to_csv(output, index=False)

    print(f"Symbols: {len(manifest)}")
    print(f"Successful: {(manifest['status'] == 'ok').sum()}")
    print(f"Failed: {(manifest['status'] != 'ok').sum()}")
    print(f"Eligible: {manifest['eligible'].astype(str).str.lower().eq('true').sum()}")
    print(f"Manifest SHA-256: {manifest_hash}")
    print(f"Saved -> {output}")


if __name__ == "__main__":
    main()
