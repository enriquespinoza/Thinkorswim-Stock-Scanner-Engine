import pandas as pd
import pytest

from src.integrations.schwab.research_history_policy import (
    normalize_research_price_history,
)


def _payload(date_ms: int, *, open_: float, high: float, low: float, close: float):
    next_day = date_ms + 24 * 60 * 60 * 1000
    return {
        "empty": False,
        "candles": [
            {
                "datetime": date_ms,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000,
            },
            {
                "datetime": next_day,
                "open": 64.0,
                "high": 65.0,
                "low": 63.5,
                "close": 64.5,
                "volume": 1100,
            },
        ],
    }


def test_known_bad_session_is_quarantined() -> None:
    timestamp = pd.Timestamp("2023-06-05 05:00:00", tz="UTC")
    payload = _payload(
        int(timestamp.timestamp() * 1000),
        open_=62.92,
        high=63.88,
        low=63.08,
        close=63.32,
    )

    bars, quarantined = normalize_research_price_history(payload, "XLC")

    assert len(bars) == 1
    assert len(quarantined) == 1
    assert quarantined.iloc[0]["timestamp"].date() == pd.Timestamp("2023-06-05").date()


def test_unknown_invalid_session_still_fails() -> None:
    timestamp = pd.Timestamp("2023-06-06 05:00:00", tz="UTC")
    payload = _payload(
        int(timestamp.timestamp() * 1000),
        open_=62.92,
        high=63.00,
        low=63.08,
        close=63.10,
    )

    with pytest.raises(ValueError, match="outside the approved quarantine"):
        normalize_research_price_history(payload, "TEST")


def test_repeated_anomaly_dates_are_quarantined() -> None:
    for date_text in ("2020-10-21 05:00:00", "2023-01-24 05:00:00"):
        timestamp = pd.Timestamp(date_text, tz="UTC")
        payload = _payload(
            int(timestamp.timestamp() * 1000),
            open_=100.0,
            high=99.0,
            low=98.0,
            close=98.5,
        )

        bars, quarantined = normalize_research_price_history(payload, "TEST")

        assert len(bars) == 1
        assert len(quarantined) == 1
        assert quarantined.iloc[0]["timestamp"].date() == timestamp.date()
