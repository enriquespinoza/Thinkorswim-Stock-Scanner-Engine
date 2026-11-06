from __future__ import annotations

import numpy as np
import pandas as pd

from config.scoring import FEATURE_GROUPS
from config.weight_research import PRIMARY_FORWARD_RETURN_HORIZON
from src.scoring.weight_research import GROUPS, evaluate_candidate


def benchmark_weight_sets() -> dict[str, dict[str, float]]:
    equal = {group: 1.0 / len(GROUPS) for group in GROUPS}
    result: dict[str, dict[str, float]] = {"equal_weight": equal}

    for group in GROUPS:
        weights = {name: 0.0 for name in GROUPS}
        weights[group] = 1.0
        result[f"{group}_only"] = weights

    return result


def _weights_from_candidate_row(row: pd.Series) -> dict[str, float]:
    return {group: float(row[group]) for group in GROUPS}


def select_ic_only_candidate(
    candidate_results: pd.DataFrame,
    fold: int,
) -> pd.Series:
    subset = candidate_results.loc[candidate_results["fold"].eq(fold)].copy()
    if subset.empty:
        raise ValueError(f"No candidate results found for fold {fold}")

    return subset.sort_values(
        ["mean_rank_ic", "mean_top_bottom_spread"],
        ascending=False,
        na_position="last",
    ).iloc[0]


def run_baseline_comparison(
    panel: pd.DataFrame,
    folds: pd.DataFrame,
    candidate_results: pd.DataFrame,
) -> pd.DataFrame:
    horizon = PRIMARY_FORWARD_RETURN_HORIZON
    forward_column = f"forward_return_{horizon}d"

    working = panel.loc[panel["scoring_complete"]].copy()
    working["session_date"] = pd.to_datetime(working["session_date"], utc=True)

    rows: list[dict[str, object]] = []
    fixed = benchmark_weight_sets()

    for fold_row in folds.itertuples(index=False):
        fold = int(fold_row.fold)
        test_start = pd.Timestamp(fold_row.test_start, tz="UTC")
        test_end = pd.Timestamp(fold_row.test_end, tz="UTC")

        test = working.loc[
            working["session_date"].between(test_start, test_end)
            & working[forward_column].notna()
        ].copy()

        model_weights = dict(fixed)

        penalized = {
            group: float(getattr(fold_row, f"weight_{group}"))
            for group in GROUPS
        }
        model_weights["optimized_penalized"] = penalized

        ic_only_row = select_ic_only_candidate(candidate_results, fold)
        model_weights["optimized_ic_only"] = _weights_from_candidate_row(ic_only_row)

        for model_name, weights in model_weights.items():
            metrics = evaluate_candidate(
                test,
                weights,
                forward_column=forward_column,
            )
            rows.append(
                {
                    "fold": fold,
                    "model": model_name,
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    **{f"weight_{group}": weights[group] for group in GROUPS},
                    **{f"test_{key}": value for key, value in metrics.items()},
                }
            )

    return pd.DataFrame(rows)


def summarize_baseline_comparison(results: pd.DataFrame) -> pd.DataFrame:
    grouped = results.groupby("model", sort=True)

    summary = grouped.agg(
        folds=("fold", "nunique"),
        mean_rank_ic=("test_mean_rank_ic", "mean"),
        median_rank_ic=("test_mean_rank_ic", "median"),
        mean_top_bottom_spread=("test_mean_top_bottom_spread", "mean"),
        mean_positive_spread_rate=("test_positive_spread_rate", "mean"),
        mean_turnover=("test_mean_turnover", "mean"),
    ).reset_index()

    positive_ic = (
        results.assign(positive_ic=results["test_mean_rank_ic"].gt(0.0))
        .groupby("model", sort=True)["positive_ic"]
        .mean()
        .rename("positive_ic_fold_rate")
        .reset_index()
    )
    summary = summary.merge(positive_ic, on="model", how="left")

    return summary.sort_values(
        ["mean_rank_ic", "mean_top_bottom_spread"],
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
