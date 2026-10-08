from __future__ import annotations

import argparse

import pandas as pd


def diagnose_symbol(symbol: str, period: str = "2y", interval: str = "1d") -> None:
    import yfinance as yf

    raw = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw = raw.reset_index()
    raw.columns = [str(column).strip().lower().replace(" ", "_") for column in raw.columns]

    timestamp_column = "date" if "date" in raw.columns else "timestamp"
    required = [timestamp_column, "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"Missing raw columns: {missing}")

    work = raw[required].copy()

    for column in ["open", "high", "low", "close", "volume"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    invalid = (
        (work["low"] > work[["open", "close", "high"]].min(axis=1))
        | (work["high"] < work[["open", "close", "low"]].max(axis=1))
        | (work["volume"] < 0)
    )

    print("=" * 96)
    print(f"RAW MARKET-DATA DIAGNOSTIC: {symbol}")
    print("=" * 96)
    print(f"Rows returned: {len(work)}")
    print(f"Rows with null OHLCV values: {int(work[['open','high','low','close','volume']].isna().any(axis=1).sum())}")
    print(f"Invalid OHLC/volume rows: {int(invalid.sum())}")

    if invalid.any():
        bad = work.loc[invalid].copy()
        bad["high_minus_max_oc"] = bad["high"] - bad[["open", "close"]].max(axis=1)
        bad["min_oc_minus_low"] = bad[["open", "close"]].min(axis=1) - bad["low"]
        print()
        print("INVALID ROWS")
        print(bad.to_string(index=False))

        positions = list(work.index[invalid])
        print()
        print("CONTEXT")
        for position in positions:
            start = max(0, position - 2)
            stop = min(len(work), position + 3)
            print()
            print(work.iloc[start:stop].to_string(index=False))
    else:
        print()
        print("No invalid rows detected in the current provider response.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect raw Yahoo Finance OHLCV rows for one symbol.")
    parser.add_argument("symbol")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--interval", default="1d")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    diagnose_symbol(args.symbol.upper(), period=args.period, interval=args.interval)
