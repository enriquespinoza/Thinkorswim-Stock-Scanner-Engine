from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config.scoring import (
    MIN_CROSS_SECTION_SIZE,
    WINSOR_LOWER_QUANTILE,
    WINSOR_UPPER_QUANTILE,
)
from config.weight_research import FORWARD_RETURN_HORIZONS


DERIVED_SIGNALS = (
    "momentum_252d_ex_20d",
    "momentum_126d_ex_20d",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test long-horizon momentum signals excluding the most recent 20 trading days."
    )
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=Path("reports/research/phase_3b"),
    )
    return parser.parse_args()


def _winsorized_zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if len(valid) < MIN_CROSS_SECTION_SIZE:
        return pd.Series(np.nan, index=series.index, dtype=float)

    lower = float(valid.quantile(WINSOR_LOWER_QUANTILE))
    upper = float(valid.quantile(WINSOR_UPPER_QUANTILE))
    clipped = numeric.clip(lower=lower, upper=upper)
    mean = float(clipped.mean(skipna=True))
    std = float(clipped.std(skipna=True, ddof=0))
    if not np.isfinite(std) or std == 0.0:
        return pd.Series(np.nan, index=series.index, dtype=float)
    return (clipped - mean) / std


def add_derived_signals(panel: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()

    # Exact price-return identity:
    # P(t-20) / P(t-252) - 1
    # = (1 + R252) / (1 + R20) - 1
    result["momentum_252d_ex_20d"] = (
        (1.0 + result["return_252d"])
        / (1.0 + result["return_20d"])
        - 1.0
    )
    result["momentum_126d_ex_20d"] = (
        (1.0 + result["return_126d"])
        / (1.0 + result["return_20d"])
        - 1.0
    )

    normalized_dates: list[pd.DataFrame] = []
    for _, cross_section in result.groupby("session_date", sort=True):
        cross_section = cross_section.copy()
        for signal in DERIVED_SIGNALS:
            cross_section[f"z_{signal}"] = _winsorized_zscore(
                cross_section[signal]
            )
        normalized_dates.append(cross_section)

    return pd.concat(normalized_dates, ignore_index=True)


def daily_metrics(
    frame: pd.DataFrame,
    *,
    signal_column: str,
    forward_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for session_date, cross_section in frame.groupby("session_date", sort=True):
        valid = cross_section.dropna(
            subset=[signal_column, forward_column]
        )
        if len(valid) < MIN_CROSS_SECTION_SIZE:
            continue

        signal_rank = valid[signal_column].rank(method="average")
        forward_rank = valid[forward_column].rank(method="average")
        rank_ic = signal_rank.corr(forward_rank)

        ordered = valid.sort_values(
            [signal_column, "symbol"],
            ascending=[False, True],
            kind="stable",
        )
        basket_size = max(1, int(len(ordered) * 0.20))
        top = ordered.head(basket_size)
        bottom = ordered.tail(basket_size)

        rows.append(
            {
                "session_date": session_date,
                "rank_ic": rank_ic,
                "top_bottom_spread": (
                    top[forward_column].mean()
                    - bottom[forward_column].mean()
                ),
            }
        )

    return pd.DataFrame(rows)


def summarize(
    panel: pd.DataFrame,
    *,
    signal: str,
    signal_column: str,
    horizon: int,
) -> dict[str, object]:
    daily = daily_metrics(
        panel,
        signal_column=signal_column,
        forward_column=f"forward_return_{horizon}d",
    )
    return {
        "signal": signal,
        "horizon_days": horizon,
        "scoring_dates": len(daily),
        "mean_rank_ic": daily["rank_ic"].mean(),
        "median_rank_ic": daily["rank_ic"].median(),
        "positive_ic_rate": (daily["rank_ic"] > 0.0).mean(),
        "mean_top_bottom_spread": daily["top_bottom_spread"].mean(),
        "positive_spread_rate": (
            daily["top_bottom_spread"] > 0.0
        ).mean(),
    }


def main() -> None:
    args = parse_args()
    panel = pd.read_csv(
        args.research_dir / "historical_scoring_panel.csv"
    )
    panel["session_date"] = pd.to_datetime(
        panel["session_date"],
        utc=True,
    )
    panel = add_derived_signals(panel)

    rows: list[dict[str, object]] = []
    comparison_signals = {
        "return_252d": "return_252d",
        "return_126d": "return_126d",
        "momentum_252d_ex_20d": "z_momentum_252d_ex_20d",
        "momentum_126d_ex_20d": "z_momentum_126d_ex_20d",
    }

    for horizon in FORWARD_RETURN_HORIZONS:
        # Raw return ranks are sufficient for the existing return features because
        # monotonic cross-sectional z-scoring preserves rank order.
        for signal, column in comparison_signals.items():
            rows.append(
                summarize(
                    panel,
                    signal=signal,
                    signal_column=column,
                    horizon=horizon,
                )
            )

    summary = pd.DataFrame(rows).sort_values(
        ["horizon_days", "mean_rank_ic"],
        ascending=[True, False],
    )

    output = args.research_dir / "long_horizon_momentum_diagnostics.csv"
    summary.to_csv(output, index=False)

    print("=" * 96)
    print("PHASE 3C LONG-HORIZON MOMENTUM DIAGNOSTICS")
    print("=" * 96)

    for horizon in FORWARD_RETURN_HORIZONS:
        view = summary.loc[summary["horizon_days"].eq(horizon)]
        print()
        print(f"{horizon}-DAY FORWARD HORIZON")
        print(view.to_string(index=False))

    print()
    print(f"Saved -> {output}")


if __name__ == "__main__":
    main()
