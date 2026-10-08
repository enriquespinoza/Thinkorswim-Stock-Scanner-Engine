import pandas as pd

from src.data.schema import normalize_daily_bars
from src.universe.eligibility import EligibilityPolicy, evaluate_basic_eligibility


def _bars(rows: int = 260, close: float = 100.0, volume: float = 200_000.0) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": volume,
        }
    )


def test_normalize_daily_bars() -> None:
    normalized = normalize_daily_bars(_bars(), "aapl")
    assert normalized.columns.tolist() == [
        "timestamp", "symbol", "open", "high", "low", "close", "volume"
    ]
    assert normalized["symbol"].unique().tolist() == ["AAPL"]
    assert str(normalized["timestamp"].dt.tz) == "UTC"


def test_basic_eligibility_passes_liquid_security() -> None:
    normalized = normalize_daily_bars(_bars(), "AAPL")
    eligible, reasons = evaluate_basic_eligibility(normalized)
    assert eligible is True
    assert reasons == ()


def test_basic_eligibility_rejects_short_history() -> None:
    normalized = normalize_daily_bars(_bars(rows=100), "AAPL")
    eligible, reasons = evaluate_basic_eligibility(normalized)
    assert eligible is False
    assert "insufficient_history" in reasons


def test_basic_eligibility_rejects_low_liquidity() -> None:
    normalized = normalize_daily_bars(_bars(volume=1_000), "TEST")
    policy = EligibilityPolicy(min_median_dollar_volume_20d=10_000_000)
    eligible, reasons = evaluate_basic_eligibility(normalized, policy)
    assert eligible is False
    assert "insufficient_dollar_volume" in reasons
