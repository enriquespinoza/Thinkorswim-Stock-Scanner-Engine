from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config.scoring import FEATURE_GROUPS, SCORING_FEATURES, SIGNAL_DIRECTIONS
from config.weight_research import FORWARD_RETURN_HORIZONS
from src.scoring.normalization import normalize_scoring_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose Phase 3 signal strength by feature, group, and horizon."
    )
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=Path("reports/research/phase_3b"),
    )
    return parser.parse_args()


def _daily_signal_metrics(
    frame: pd.DataFrame,
    *,
    signal_column: str,
    forward_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for session_date, cross_section in frame.groupby("session_date", sort=True):
        valid = cross_section.dropna(subset=[signal_column, forward_column])
        if len(valid) < 50:
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


def _summarize_signal(
    frame: pd.DataFrame,
    *,
    signal_name: str,
    signal_column: str,
    signal_type: str,
    horizon: int,
    feature_group: str = "",
    signal_direction: int | None = None,
) -> dict[str, object]:
    forward_column = f"forward_return_{horizon}d"
    daily = _daily_signal_metrics(
        frame,
        signal_column=signal_column,
        forward_column=forward_column,
    )

    rank_ic_std = daily["rank_ic"].std(ddof=0)
    mean_rank_ic = daily["rank_ic"].mean()

    return {
        "signal_type": signal_type,
        "signal": signal_name,
        "feature_group": feature_group,
        "signal_direction": signal_direction,
        "horizon_days": horizon,
        "scoring_dates": len(daily),
        "mean_rank_ic": mean_rank_ic,
        "median_rank_ic": daily["rank_ic"].median(),
        "positive_ic_rate": (daily["rank_ic"] > 0.0).mean(),
        "mean_top_bottom_spread": daily["top_bottom_spread"].mean(),
        "positive_spread_rate": (
            daily["top_bottom_spread"] > 0.0
        ).mean(),
        "rank_ic_std": rank_ic_std,
        "rank_ic_ir": (
            mean_rank_ic / rank_ic_std
            if pd.notna(rank_ic_std) and rank_ic_std > 0.0
            else np.nan
        ),
    }


def _normalized_panel(panel: pd.DataFrame) -> pd.DataFrame:
    normalized_dates: list[pd.DataFrame] = []

    for _, cross_section in panel.groupby("session_date", sort=True):
        normalized = normalize_scoring_snapshot(cross_section)
        for group, features in FEATURE_GROUPS.items():
            normalized[f"group_{group}"] = normalized[
                [f"z_{feature}" for feature in features]
            ].mean(axis=1, skipna=False)
        normalized_dates.append(normalized)

    return pd.concat(normalized_dates, ignore_index=True)


def _group_correlation_summary(panel: pd.DataFrame) -> pd.DataFrame:
    group_columns = [f"group_{group}" for group in FEATURE_GROUPS]
    matrices = []

    for _, cross_section in panel.groupby("session_date", sort=True):
        valid = cross_section[group_columns].dropna()
        if len(valid) < 50:
            continue
        matrices.append(valid.corr(method="pearson"))

    if not matrices:
        return pd.DataFrame()

    stacked = np.stack([matrix.to_numpy() for matrix in matrices], axis=0)
    mean_matrix = np.nanmean(stacked, axis=0)

    return pd.DataFrame(
        mean_matrix,
        index=group_columns,
        columns=group_columns,
    )


def _feature_correlation_summary(panel: pd.DataFrame) -> pd.DataFrame:
    feature_columns = [f"z_{feature}" for feature in SCORING_FEATURES]
    matrices = []

    for _, cross_section in panel.groupby("session_date", sort=True):
        valid = cross_section[feature_columns].dropna()
        if len(valid) < 50:
            continue
        matrices.append(valid.corr(method="pearson"))

    if not matrices:
        return pd.DataFrame()

    stacked = np.stack([matrix.to_numpy() for matrix in matrices], axis=0)
    mean_matrix = np.nanmean(stacked, axis=0)

    return pd.DataFrame(
        mean_matrix,
        index=SCORING_FEATURES,
        columns=SCORING_FEATURES,
    )


def _feature_group_map() -> dict[str, str]:
    return {
        feature: group
        for group, features in FEATURE_GROUPS.items()
        for feature in features
    }


def main() -> None:
    args = parse_args()
    panel_path = args.research_dir / "historical_scoring_panel.csv"
    panel = pd.read_csv(panel_path)
    panel["session_date"] = pd.to_datetime(panel["session_date"], utc=True)

    normalized = _normalized_panel(panel)

    rows: list[dict[str, object]] = []
    feature_groups = _feature_group_map()

    for horizon in FORWARD_RETURN_HORIZONS:
        for group in FEATURE_GROUPS:
            rows.append(
                _summarize_signal(
                    normalized,
                    signal_name=group,
                    signal_column=f"group_{group}",
                    signal_type="group",
                    horizon=horizon,
                    feature_group=group,
                )
            )

        for feature in SCORING_FEATURES:
            rows.append(
                _summarize_signal(
                    normalized,
                    signal_name=feature,
                    signal_column=f"z_{feature}",
                    signal_type="feature",
                    horizon=horizon,
                    feature_group=feature_groups[feature],
                    signal_direction=SIGNAL_DIRECTIONS[feature],
                )
            )

    summary = pd.DataFrame(rows).sort_values(
        ["horizon_days", "signal_type", "mean_rank_ic"],
        ascending=[True, True, False],
    )

    correlations = _group_correlation_summary(normalized)
    feature_correlations = _feature_correlation_summary(normalized)

    summary_path = args.research_dir / "signal_diagnostics.csv"
    correlation_path = args.research_dir / "group_correlations.csv"
    feature_correlation_path = args.research_dir / "feature_correlations.csv"

    summary.to_csv(summary_path, index=False)
    correlations.to_csv(correlation_path)
    feature_correlations.to_csv(feature_correlation_path)

    print("=" * 100)
    print("PHASE 3C SIGNAL DIAGNOSTICS")
    print("=" * 100)

    for horizon in FORWARD_RETURN_HORIZONS:
        group_view = summary.loc[
            (summary["signal_type"] == "group")
            & (summary["horizon_days"] == horizon)
        ]
        print()
        print(f"{horizon}-DAY GROUP SIGNALS")
        print(
            group_view[
                [
                    "signal",
                    "mean_rank_ic",
                    "median_rank_ic",
                    "positive_ic_rate",
                    "mean_top_bottom_spread",
                    "positive_spread_rate",
                ]
            ].to_string(index=False)
        )

    for horizon in FORWARD_RETURN_HORIZONS:
        feature_view = summary.loc[
            (summary["signal_type"] == "feature")
            & (summary["horizon_days"] == horizon)
        ].sort_values("mean_rank_ic", ascending=False)

        print()
        print(f"{horizon}-DAY INDIVIDUAL FEATURE SIGNALS")
        print(
            feature_view[
                [
                    "feature_group",
                    "signal",
                    "signal_direction",
                    "mean_rank_ic",
                    "median_rank_ic",
                    "positive_ic_rate",
                    "rank_ic_ir",
                    "mean_top_bottom_spread",
                    "positive_spread_rate",
                ]
            ].to_string(index=False)
        )

    print()
    print("MEAN CROSS-SECTIONAL GROUP CORRELATIONS")
    print(correlations.to_string())
    print()
    print(f"Saved -> {summary_path}")
    print(f"Saved -> {correlation_path}")
    print(f"Saved -> {feature_correlation_path}")


if __name__ == "__main__":
    main()
