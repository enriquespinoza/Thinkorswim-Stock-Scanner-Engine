from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config.scoring import MIN_CROSS_SECTION_SIZE
from config.weight_research import FORWARD_RETURN_HORIZONS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare compact, pre-specified alpha candidates for Scanner Score V1 research."
    )
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=Path("reports/research/phase_3b"),
    )
    return parser.parse_args()


def _add_candidate_signals(panel: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()
    result["momentum_252d_ex_20d"] = (
        (1.0 + result["return_252d"])
        / (1.0 + result["return_20d"])
        - 1.0
    )

    parts: list[pd.DataFrame] = []
    for _, cross_section in result.groupby("session_date", sort=True):
        cross_section = cross_section.copy()
        cross_section["rank_return_252d"] = cross_section["return_252d"].rank(
            method="average",
            pct=True,
        )
        cross_section["rank_momentum_252d_ex_20d"] = cross_section[
            "momentum_252d_ex_20d"
        ].rank(method="average", pct=True)
        cross_section["rank_ema_50_to_200"] = cross_section[
            "ema_50_to_200"
        ].rank(method="average", pct=True)

        cross_section["compact_alpha_blend"] = (
            cross_section["rank_momentum_252d_ex_20d"]
            + cross_section["rank_ema_50_to_200"]
        ) / 2.0
        parts.append(cross_section)

    return pd.concat(parts, ignore_index=True)


def _metrics(
    frame: pd.DataFrame,
    *,
    signal_column: str,
    forward_column: str,
) -> dict[str, float]:
    rows: list[dict[str, float]] = []

    for _, cross_section in frame.groupby("session_date", sort=True):
        valid = cross_section.dropna(subset=[signal_column, forward_column])
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
                "rank_ic": float(rank_ic),
                "spread": float(
                    top[forward_column].mean()
                    - bottom[forward_column].mean()
                ),
            }
        )

    daily = pd.DataFrame(rows)
    if daily.empty:
        return {
            "mean_rank_ic": np.nan,
            "median_rank_ic": np.nan,
            "positive_ic_rate": np.nan,
            "mean_top_bottom_spread": np.nan,
            "positive_spread_rate": np.nan,
        }

    return {
        "mean_rank_ic": float(daily["rank_ic"].mean()),
        "median_rank_ic": float(daily["rank_ic"].median()),
        "positive_ic_rate": float((daily["rank_ic"] > 0.0).mean()),
        "mean_top_bottom_spread": float(daily["spread"].mean()),
        "positive_spread_rate": float((daily["spread"] > 0.0).mean()),
    }


def main() -> None:
    args = parse_args()
    panel = pd.read_csv(args.research_dir / "historical_scoring_panel.csv")
    folds = pd.read_csv(args.research_dir / "walk_forward_folds.csv")

    panel["session_date"] = pd.to_datetime(panel["session_date"], utc=True)
    panel = _add_candidate_signals(panel)

    candidates = {
        "return_252d": "rank_return_252d",
        "momentum_252d_ex_20d": "rank_momentum_252d_ex_20d",
        "ema_50_to_200": "rank_ema_50_to_200",
        "momentum_12_1_plus_slow_trend": "compact_alpha_blend",
    }

    rows: list[dict[str, object]] = []

    for fold in folds.to_dict(orient="records"):
        fold_id = int(fold["fold"])
        start = pd.Timestamp(str(fold["test_start"]), tz="UTC")
        end = pd.Timestamp(str(fold["test_end"]), tz="UTC")
        test = panel.loc[
            panel["session_date"].ge(start)
            & panel["session_date"].le(end)
        ]

        for horizon in FORWARD_RETURN_HORIZONS:
            forward_column = f"forward_return_{horizon}d"
            for name, signal_column in candidates.items():
                metrics = _metrics(
                    test,
                    signal_column=signal_column,
                    forward_column=forward_column,
                )
                rows.append(
                    {
                        "fold": fold_id,
                        "candidate": name,
                        "horizon_days": horizon,
                        **metrics,
                    }
                )

    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["horizon_days", "candidate"], sort=False)
        .agg(
            folds=("fold", "nunique"),
            mean_rank_ic=("mean_rank_ic", "mean"),
            median_rank_ic=("median_rank_ic", "mean"),
            positive_ic_rate=("positive_ic_rate", "mean"),
            mean_top_bottom_spread=("mean_top_bottom_spread", "mean"),
            positive_spread_rate=("positive_spread_rate", "mean"),
        )
        .reset_index()
        .sort_values(
            ["horizon_days", "mean_rank_ic", "mean_top_bottom_spread"],
            ascending=[True, False, False],
        )
    )

    # Mean cross-sectional correlation between the two compact alpha legs.
    correlations: list[float] = []
    for _, cross_section in panel.groupby("session_date", sort=True):
        valid = cross_section[
            ["rank_momentum_252d_ex_20d", "rank_ema_50_to_200"]
        ].dropna()
        if len(valid) < MIN_CROSS_SECTION_SIZE:
            continue
        correlations.append(
            float(
                valid["rank_momentum_252d_ex_20d"].corr(
                    valid["rank_ema_50_to_200"]
                )
            )
        )

    detail_path = args.research_dir / "compact_alpha_candidate_folds.csv"
    summary_path = args.research_dir / "compact_alpha_candidate_summary.csv"
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)

    print("=" * 100)
    print("PHASE 3C COMPACT ALPHA CANDIDATE COMPARISON")
    print("=" * 100)

    for horizon in FORWARD_RETURN_HORIZONS:
        view = summary.loc[summary["horizon_days"].eq(horizon)]
        print()
        print(f"{horizon}-DAY FORWARD HORIZON")
        print(view.to_string(index=False))

    print()
    if correlations:
        print(
            "Mean cross-sectional rank correlation "
            "(12-1 momentum vs slow trend): "
            f"{np.mean(correlations):.4f}"
        )

    print()
    print(f"Saved -> {detail_path}")
    print(f"Saved -> {summary_path}")


if __name__ == "__main__":
    main()
