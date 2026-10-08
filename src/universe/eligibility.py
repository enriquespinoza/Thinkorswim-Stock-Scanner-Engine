from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EligibilityPolicy:
    min_price: float = 5.0
    min_history_rows: int = 252
    min_median_dollar_volume_20d: float = 10_000_000.0


def evaluate_basic_eligibility(
    bars: pd.DataFrame,
    policy: EligibilityPolicy = EligibilityPolicy(),
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if len(bars) < policy.min_history_rows:
        reasons.append("insufficient_history")
        return False, tuple(reasons)

    if float(bars["close"].iloc[-1]) < policy.min_price:
        reasons.append("price_below_minimum")

    trailing = bars.tail(20)
    median_dollar_volume = float((trailing["close"] * trailing["volume"]).median())
    if median_dollar_volume < policy.min_median_dollar_volume_20d:
        reasons.append("insufficient_dollar_volume")

    return not reasons, tuple(reasons)
