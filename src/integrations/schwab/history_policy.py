from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

import pandas as pd

from src.integrations.schwab.provider import SchwabDailyBarProvider, SchwabHistoryResult


@dataclass(frozen=True)
class SchwabHistoryResolution:
    selected: SchwabHistoryResult
    initial: SchwabHistoryResult
    fallback: SchwabHistoryResult | None
    request_mode: str

    @property
    def initial_rows(self) -> int:
        return len(self.initial.bars)

    @property
    def fallback_rows(self) -> int | None:
        return None if self.fallback is None else len(self.fallback.bars)


def _trim_to_requested_window(
    result: SchwabHistoryResult,
    *,
    start_datetime: datetime,
    end_datetime: datetime,
) -> SchwabHistoryResult:
    bars = result.bars.copy()
    timestamps = pd.to_datetime(bars["timestamp"], utc=True)

    start = pd.Timestamp(start_datetime)
    end = pd.Timestamp(end_datetime)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    else:
        end = end.tz_convert("UTC")

    trimmed = bars.loc[(timestamps >= start) & (timestamps <= end)].reset_index(drop=True)

    return replace(
        result,
        bars=trimmed,
    )


def resolve_daily_history(
    provider: SchwabDailyBarProvider,
    *,
    provider_symbol: str,
    canonical_symbol: str,
    start_datetime: datetime,
    end_datetime: datetime,
    minimum_rows: int,
) -> SchwabHistoryResolution:
    """Prefer bounded history, with one unbounded recovery request when needed.

    The unbounded response is only a recovery mechanism. If selected, its bars
    are trimmed back to the originally requested window so all symbols retain a
    consistent research horizon.
    """
    initial = provider.fetch(
        provider_symbol,
        canonical_symbol,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    if len(initial.bars) >= minimum_rows:
        return SchwabHistoryResolution(
            selected=initial,
            initial=initial,
            fallback=None,
            request_mode="bounded",
        )

    fallback_full = provider.fetch(
        provider_symbol,
        canonical_symbol,
        start_datetime=None,
        end_datetime=None,
    )
    fallback = _trim_to_requested_window(
        fallback_full,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    if len(fallback.bars) > len(initial.bars):
        selected = fallback
        mode = "unbounded_fallback_trimmed"
    else:
        selected = initial
        mode = "bounded_shorter_or_equal_fallback"

    return SchwabHistoryResolution(
        selected=selected,
        initial=initial,
        fallback=fallback,
        request_mode=mode,
    )
