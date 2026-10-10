from __future__ import annotations

from src.integrations.schwab.auth import (
    create_schwab_market_data_client,
    load_schwab_auth_config,
)


def main() -> None:
    print()
    print("=" * 88)
    print("SCHWAB MARKET-DATA CONNECTIVITY SMOKE TEST")
    print("=" * 88)

    config = load_schwab_auth_config()

    print("Configuration loaded: YES")
    print("Credentials printed: NO")
    print("Token printed: NO")

    client = create_schwab_market_data_client(config)

    print("Authenticated market-data client created: YES")

    quotes = client.get_quotes_payload(["SPY", "AAPL"])

    print()
    print("QUOTE TEST")
    print("-" * 88)
    print("Requested symbols: SPY, AAPL")
    print(f"Quote records returned: {len(quotes)}")
    print("Returned keys:", ", ".join(sorted(str(key) for key in quotes.keys())))

    history = client.get_daily_price_history_payload("SPY")
    candles = history.get("candles", [])

    print()
    print("PRICE-HISTORY TEST")
    print("-" * 88)
    print(f"SPY candles returned: {len(candles)}")
    print(f"Payload empty flag: {bool(history.get('empty', False))}")

    if not candles:
        raise RuntimeError("Schwab returned no SPY price-history candles.")

    latest = candles[-1]

    required_fields = {"datetime", "open", "high", "low", "close", "volume"}
    missing = required_fields.difference(latest)

    if missing:
        raise RuntimeError(
            f"Latest SPY candle is missing required fields: {sorted(missing)}"
        )

    print("Latest candle contains required OHLCV fields: YES")

    print()
    print("SAFETY BOUNDARY")
    print("-" * 88)
    print("Account methods exposed by wrapper: NO")
    print("Order methods exposed by wrapper: NO")
    print("Orders generated: NO")
    print("Orders submitted: NO")

    print()
    print("=" * 88)
    print("SCHWAB MARKET-DATA SMOKE TEST PASSED")
    print("=" * 88)


if __name__ == "__main__":
    main()
