import pandas as pd

from scripts.audit_cross_provider import compare_symbol


def _bars(symbol: str, hour: int) -> pd.DataFrame:
    dates = pd.date_range("2026-10-01", periods=3, freq="B", tz="UTC")
    timestamps = dates + pd.to_timedelta(hour, unit="h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": symbol,
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200],
        }
    )


def test_cross_provider_audit_matches_same_session_with_different_utc_hours() -> None:
    yahoo = _bars("TEST", 0)
    schwab = _bars("TEST", 4)

    result = compare_symbol(
        yahoo,
        schwab,
        symbol="TEST",
        price_tolerance_bps=5.0,
    )

    assert result["overlap_rows"] == 3
    assert result["latest_date_match"] is True
    assert result["median_timestamp_offset_hours"] == 4.0
    assert result["max_close_diff_bps"] == 0.0
    assert result["volume_match_rate"] == 1.0
    assert result["status"] == "ok"


def test_cross_provider_audit_flags_material_close_difference() -> None:
    yahoo = _bars("TEST", 0)
    schwab = _bars("TEST", 4)
    schwab.loc[2, "close"] = 105.0

    result = compare_symbol(
        yahoo,
        schwab,
        symbol="TEST",
        price_tolerance_bps=5.0,
    )

    assert result["overlap_rows"] == 3
    assert result["status"] == "review"
    assert result["max_close_diff_bps"] > 5.0
