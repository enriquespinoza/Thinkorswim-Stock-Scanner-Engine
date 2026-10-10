from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config.scoring import FEATURE_GROUPS
from config.weight_research import PRIMARY_FORWARD_RETURN_HORIZON
from src.scoring.weight_research import GROUPS, evaluate_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Phase 3B optimized weights against simple out-of-sample baselines."
    )
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=Path("reports/research/phase_3b"),
    )
    return parser.parse_args()


def _weights(**overrides: float) -> dict[str, float]:
    result = {group: 0.0 for group in GROUPS}
    result.update(overrides)
    return result


def _equal_weights() -> dict[str, float]:
    value = 1.0 / len(GROUPS)
    return {group: value for group in GROUPS}


def _test_slice(
    panel: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    forward_column: str,
) -> pd.DataFrame:
    session = pd.to_datetime(panel["session_date"], utc=True)
    return panel.loc[
        panel["scoring_complete"].astype(bool)
        & session.ge(start)
        & session.le(end)
        & panel[forward_column].notna()
    ].copy()


def main() -> None:
    args = parse_args()

    panel_path = args.research_dir / "historical_scoring_panel.csv"
    folds_path = args.research_dir / "walk_forward_folds.csv"
    candidates_path = args.research_dir / "candidate_results.csv"

    panel = pd.read_csv(panel_path)
    folds = pd.read_csv(folds_path)
    candidates = pd.read_csv(candidates_path)

    forward_column = f"forward_return_{PRIMARY_FORWARD_RETURN_HORIZON}d"

    baseline_models: dict[str, dict[str, float]] = {
        "equal_weight": _equal_weights(),
        **{
            f"{group}_only": _weights(**{group: 1.0})
            for group in GROUPS
        },
    }

    rows: list[dict[str, object]] = []

    for fold in folds.to_dict(orient="records"):
        fold_id = int(fold["fold"])
        test_start = pd.Timestamp(str(fold["test_start"]), tz="UTC")
        test_end = pd.Timestamp(str(fold["test_end"]), tz="UTC")

        test = _test_slice(
            panel,
            start=test_start,
            end=test_end,
            forward_column=forward_column,
        )

        penalized_weights = {
            group: float(fold[f"weight_{group}"])
            for group in GROUPS
        }

        fold_candidates = candidates.loc[
            candidates["fold"].astype(int).eq(fold_id)
        ].copy()

        ic_best = fold_candidates.sort_values(
            ["mean_rank_ic", "mean_top_bottom_spread"],
            ascending=False,
            na_position="last",
        ).iloc[0]
        ic_weights = {
            group: float(ic_best[group])
            for group in GROUPS
        }

        models = {
            "optimized_penalized": penalized_weights,
            "optimized_ic_only": ic_weights,
            **baseline_models,
        }

        for model_name, weights in models.items():
            metrics = evaluate_candidate(
                test,
                weights,
                forward_column=forward_column,
            )
            rows.append(
                {
                    "fold": fold_id,
                    "model": model_name,
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    **{f"weight_{group}": weights[group] for group in GROUPS},
                    **metrics,
                }
            )

    detail = pd.DataFrame(rows)

    summary = (
        detail.groupby("model", sort=False)
        .agg(
            folds=("fold", "nunique"),
            mean_rank_ic=("mean_rank_ic", "mean"),
            median_rank_ic=("median_rank_ic", "mean"),
            mean_top_bottom_spread=("mean_top_bottom_spread", "mean"),
            positive_spread_rate=("positive_spread_rate", "mean"),
            mean_turnover=("mean_turnover", "mean"),
        )
        .reset_index()
    )

    summary = summary.sort_values(
        ["mean_rank_ic", "mean_top_bottom_spread"],
        ascending=False,
    ).reset_index(drop=True)

    detail_path = args.research_dir / "baseline_comparison_folds.csv"
    summary_path = args.research_dir / "baseline_comparison_summary.csv"

    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)

    print("=" * 88)
    print("PHASE 3B BASELINE COMPARISON")
    print("=" * 88)
    print(summary.to_string(index=False))
    print()
    print(f"Saved -> {detail_path}")
    print(f"Saved -> {summary_path}")


if __name__ == "__main__":
    main()
