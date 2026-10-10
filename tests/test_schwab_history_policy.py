from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.integrations.schwab.history_policy import resolve_daily_history


@dataclass
class Result:
    bars: pd.DataFrame


class FakeProvider:
    def __init__(self, frames):
        self.frames = list(frames)
        self.calls = []

    def fetch(self, provider_symbol, canonical_symbol, *, start_datetime, end_datetime):
        self.calls.append((provider_symbol, canonical_symbol, start_datetime, end_datetime))
        return Result(bars=self.frames.pop(0))


def _frame(start: datetime, rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start, periods=rows, freq="D", tz="UTC"),
        }
    )


def test_adequate_bounded_history_does_not_retry() -> None:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=299)
    provider = FakeProvider([_frame(start, 300)])

    result = resolve_daily_history(
        provider,
        provider_symbol="TEST",
        canonical_symbol="TEST",
        start_datetime=start,
        end_datetime=end,
        minimum_rows=252,
    )

    assert result.request_mode == "bounded"
    assert result.initial_rows == 300
    assert result.fallback is None
    assert len(provider.calls) == 1


def test_short_bounded_history_uses_trimmed_unbounded_fallback() -> None:
    requested_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    requested_end = datetime(2025, 10, 1, tzinfo=timezone.utc)

    short = _frame(requested_start, 1)
    full = _frame(datetime(2020, 1, 1, tzinfo=timezone.utc), 2200)
    provider = FakeProvider([short, full])

    result = resolve_daily_history(
        provider,
        provider_symbol="TEST",
        canonical_symbol="TEST",
        start_datetime=requested_start,
        end_datetime=requested_end,
        minimum_rows=252,
    )

    assert result.request_mode == "unbounded_fallback_trimmed"
    assert result.initial_rows == 1
    assert result.fallback_rows is not None
    assert len(result.selected.bars) == result.fallback_rows
    assert result.selected.bars["timestamp"].min() >= pd.Timestamp(requested_start)
    assert result.selected.bars["timestamp"].max() <= pd.Timestamp(requested_end)
    assert provider.calls[1][2] is None
    assert provider.calls[1][3] is None


def test_short_history_is_not_inflated_when_trimmed_fallback_is_not_longer() -> None:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=6)

    short = _frame(start, 7)
    full = _frame(start, 7)
    provider = FakeProvider([short, full])

    result = resolve_daily_history(
        provider,
        provider_symbol="TEST",
        canonical_symbol="TEST",
        start_datetime=start,
        end_datetime=end,
        minimum_rows=252,
    )

    assert result.request_mode == "bounded_shorter_or_equal_fallback"
    assert result.initial_rows == 7
    assert result.fallback_rows == 7
    assert len(result.selected.bars) == 7
