from __future__ import annotations

import argparse

from src.integrations.schwab.auth import (
    create_schwab_market_data_client,
    load_schwab_auth_config,
)
from src.integrations.schwab.provider import normalize_schwab_price_history
from src.universe.symbols import to_schwab_symbol


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Schwab symbol mapping and daily price history."
    )
    parser.add_argument("symbols", nargs="+")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_schwab_auth_config()
    client = create_schwab_market_data_client(config)

    print("=" * 88)
    print("SCHWAB SYMBOL DIAGNOSTIC")
    print("=" * 88)

    failures = 0

    for canonical in args.symbols:
        canonical = canonical.strip().upper()
        schwab_symbol = to_schwab_symbol(canonical)

        try:
            payload = client.get_daily_price_history_payload(schwab_symbol)
            bars = normalize_schwab_price_history(payload, canonical)

            print(
                f"{canonical:8s} -> {schwab_symbol:8s} "
                f"rows={len(bars):4d} "
                f"first={bars['timestamp'].min().date()} "
                f"last={bars['timestamp'].max().date()} "
                "PASS"
            )
        except Exception as exc:
            failures += 1
            print(
                f"{canonical:8s} -> {schwab_symbol:8s} "
                f"FAIL: {type(exc).__name__}: {exc}"
            )

    if failures:
        raise SystemExit(f"SCHWAB SYMBOL DIAGNOSTIC FAILED: {failures} symbol(s)")

    print()
    print("SCHWAB SYMBOL DIAGNOSTIC PASSED")


if __name__ == "__main__":
    main()
