from datetime import datetime, timezone

import pandas as pd

from src.integrations.schwab.provider import normalize_schwab_price_history


def test_normalize_schwab_price_history() -> None:
    payload = {
        "symbol": "AAPL",
        "empty": False,
        "candles": [
            {
                "datetime": 1760000000000,
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1234567,
            },
            {
                "datetime": 1760086400000,
                "open": 101.0,
                "high": 103.0,
                "low": 100.0,
                "close": 102.0,
                "volume": 2345678,
            },
        ],
    }

    bars = normalize_schwab_price_history(payload, "AAPL")

    assert bars.columns.tolist() == [
        "timestamp", "symbol", "open", "high", "low", "close", "volume"
    ]
    assert bars["symbol"].tolist() == ["AAPL", "AAPL"]
    assert str(bars["timestamp"].dt.tz) == "UTC"
    assert bars["close"].tolist() == [101.0, 102.0]


def test_empty_schwab_history_is_rejected() -> None:
    payload = {"symbol": "AAPL", "empty": True, "candles": []}

    try:
        normalize_schwab_price_history(payload, "AAPL")
    except ValueError as exc:
        assert "empty price history" in str(exc)
    else:
        raise AssertionError("empty history should have raised")
