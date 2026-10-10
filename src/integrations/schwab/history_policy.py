from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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


def resolve_daily_history(
    provider: SchwabDailyBarProvider,
    *,
    provider_symbol: str,
    canonical_symbol: str,
    start_datetime: datetime,
    end_datetime: datetime,
    minimum_rows: int,
) -> SchwabHistoryResolution:
    """Prefer the bounded request, but verify suspiciously short histories.

    If the bounded result has fewer than minimum_rows observations, make one
    unbounded request and select whichever response contains more history.
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

    fallback = provider.fetch(
        provider_symbol,
        canonical_symbol,
        start_datetime=None,
        end_datetime=None,
    )

    if len(fallback.bars) > len(initial.bars):
        selected = fallback
        mode = "unbounded_fallback"
    else:
        selected = initial
        mode = "bounded_shorter_or_equal_fallback"

    return SchwabHistoryResolution(
        selected=selected,
        initial=initial,
        fallback=fallback,
        request_mode=mode,
    )
