from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from config.data_sources import (
    SCHWAB_REFERENCE_MANIFEST_DIR,
    SCHWAB_REFERENCE_NORMALIZED_DIR,
    SCHWAB_REFERENCE_RAW_DIR,
)
from config.features import REFERENCE_SYMBOLS
from src.data.provider_artifacts import save_normalized_bars, save_raw_json
from src.integrations.schwab.auth import (
    create_schwab_market_data_client,
    load_schwab_auth_config,
)
from src.integrations.schwab.provider import SchwabDailyBarProvider
from src.utils.hashing import stable_dataframe_hash


def main() -> None:
    config = load_schwab_auth_config()
    client = create_schwab_market_data_client(config)
    provider = SchwabDailyBarProvider(client)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=800)

    rows = []

    for symbol in REFERENCE_SYMBOLS:
        raw_path = SCHWAB_REFERENCE_RAW_DIR / f"{symbol}.json"
        normalized_path = SCHWAB_REFERENCE_NORMALIZED_DIR / f"{symbol}_1d.csv"

        result = provider.fetch(
            symbol,
            symbol,
            start_datetime=start,
            end_datetime=end,
        )

        raw_hash = save_raw_json(result.raw_payload, raw_path)
        normalized_hash = save_normalized_bars(result.bars, normalized_path)

        rows.append(
            {
                "symbol": symbol,
                "rows": len(result.bars),
                "raw_payload_hash": raw_hash,
                "normalized_data_hash": normalized_hash,
                "raw_path": str(raw_path),
                "normalized_path": str(normalized_path),
            }
        )

    manifest = pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)
    manifest_hash = stable_dataframe_hash(manifest)
    manifest["manifest_hash"] = manifest_hash

    SCHWAB_REFERENCE_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    output = SCHWAB_REFERENCE_MANIFEST_DIR / "reference_manifest.csv"
    manifest.to_csv(output, index=False)

    print(f"Reference symbols: {len(manifest)}")
    print(f"Minimum rows: {int(manifest['rows'].min())}")
    print(f"Maximum rows: {int(manifest['rows'].max())}")
    print(f"Manifest SHA-256: {manifest_hash}")
    print(f"Saved -> {output}")


if __name__ == "__main__":
    main()
