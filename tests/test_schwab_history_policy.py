from dataclasses import dataclass

import pandas as pd

from src.integrations.schwab.history_policy import resolve_daily_history


@dataclass
class Result:
    bars: pd.DataFrame


class FakeProvider:
    def __init__(self, row_counts):
        self.row_counts = list(row_counts)
        self.calls = []

    def fetch(self, provider_symbol, canonical_symbol, *, start_datetime, end_datetime):
        self.calls.append((provider_symbol, canonical_symbol, start_datetime, end_datetime))
        rows = self.row_counts.pop(0)
        return Result(bars=pd.DataFrame({"x": range(rows)}))


def test_adequate_bounded_history_does_not_retry() -> None:
    provider = FakeProvider([300])
    result = resolve_daily_history(
        provider,
        provider_symbol="TEST",
        canonical_symbol="TEST",
        start_datetime=object(),
        end_datetime=object(),
        minimum_rows=252,
    )
    assert result.request_mode == "bounded"
    assert result.initial_rows == 300
    assert result.fallback is None
    assert len(provider.calls) == 1


def test_short_bounded_history_uses_longer_unbounded_fallback() -> None:
    provider = FakeProvider([1, 551])
    result = resolve_daily_history(
        provider,
        provider_symbol="TEST",
        canonical_symbol="TEST",
        start_datetime=object(),
        end_datetime=object(),
        minimum_rows=252,
    )
    assert result.request_mode == "unbounded_fallback"
    assert result.initial_rows == 1
    assert result.fallback_rows == 551
    assert len(result.selected.bars) == 551
    assert provider.calls[1][2] is None
    assert provider.calls[1][3] is None


def test_short_history_is_not_inflated_when_fallback_is_not_longer() -> None:
    provider = FakeProvider([7, 7])
    result = resolve_daily_history(
        provider,
        provider_symbol="TEST",
        canonical_symbol="TEST",
        start_datetime=object(),
        end_datetime=object(),
        minimum_rows=252,
    )
    assert result.request_mode == "bounded_shorter_or_equal_fallback"
    assert result.initial_rows == 7
    assert result.fallback_rows == 7
    assert len(result.selected.bars) == 7
