from __future__ import annotations

from itertools import product

import numpy as np
import pandas as pd

from config.scoring import FEATURE_GROUPS
from config.weight_research import (
    BOTTOM_QUANTILE,
    MIN_TRAINING_DATES,
    PRIMARY_FORWARD_RETURN_HORIZON,
    TEST_WINDOW_DATES,
    TOP_QUANTILE,
    TURNOVER_PENALTY,
    WEIGHT_STEP,
)


GROUPS = tuple(FEATURE_GROUPS)


def generate_weight_grid(step: float = WEIGHT_STEP) -> list[dict[str, float]]:
    units = round(1.0 / step)
    if not np.isclose(units * step, 1.0):
        raise ValueError("Weight step must divide 1.0 exactly")

    candidates: list[dict[str, float]] = []
    for values in product(range(units + 1), repeat=len(GROUPS)):
        if sum(values) != units:
            continue
        candidates.append(
            {
                group: value / units
                for group, value in zip(GROUPS, values, strict=True)
            }
        )
    return candidates


def add_composite_score(
    frame: pd.DataFrame,
    weights: dict[str, float],
) -> pd.DataFrame:
    result = frame.copy()
    score = pd.Series(0.0, index=result.index)

    for group in GROUPS:
        score = score + result[f"group_{group}"] * float(weights[group])

    result["research_score"] = score
    return result


def _daily_metrics(
    frame: pd.DataFrame,
    *,
    forward_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, float | pd.Timestamp]] = []
    previous_top: set[str] | None = None

    for session_date, cross_section in frame.groupby("session_date", sort=True):
        valid = cross_section.dropna(subset=["research_score", forward_column]).copy()
        if len(valid) < 50:
            continue

        ic = valid["research_score"].corr(valid[forward_column], method="spearman")

        valid = valid.sort_values("research_score", ascending=False)
        basket_size = max(1, int(len(valid) * TOP_QUANTILE))
        bottom_size = max(1, int(len(valid) * BOTTOM_QUANTILE))

        top = valid.head(basket_size)
        bottom = valid.tail(bottom_size)
        spread = float(top[forward_column].mean() - bottom[forward_column].mean())

        top_symbols = set(top["symbol"].astype(str))
        turnover = np.nan
        if previous_top is not None:
            overlap = len(top_symbols & previous_top)
            turnover = 1.0 - overlap / max(1, len(top_symbols))
        previous_top = top_symbols

        rows.append(
            {
                "session_date": session_date,
                "rank_ic": float(ic) if pd.notna(ic) else np.nan,
                "top_bottom_spread": spread,
                "turnover": turnover,
            }
        )

    return pd.DataFrame(rows)


def evaluate_candidate(
    frame: pd.DataFrame,
    weights: dict[str, float],
    *,
    forward_column: str,
) -> dict[str, float]:
    scored = add_composite_score(frame, weights)
    daily = _daily_metrics(scored, forward_column=forward_column)

    if daily.empty:
        return {
            "mean_rank_ic": np.nan,
            "median_rank_ic": np.nan,
            "mean_top_bottom_spread": np.nan,
            "positive_spread_rate": np.nan,
            "mean_turnover": np.nan,
            "objective": np.nan,
        }

    mean_ic = float(daily["rank_ic"].mean())
    mean_turnover = float(daily["turnover"].mean(skipna=True))

    return {
        "mean_rank_ic": mean_ic,
        "median_rank_ic": float(daily["rank_ic"].median()),
        "mean_top_bottom_spread": float(daily["top_bottom_spread"].mean()),
        "positive_spread_rate": float((daily["top_bottom_spread"] > 0.0).mean()),
        "mean_turnover": mean_turnover,
        "objective": mean_ic - TURNOVER_PENALTY * mean_turnover,
    }


def walk_forward_weight_research(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    horizon = PRIMARY_FORWARD_RETURN_HORIZON
    forward_column = f"forward_return_{horizon}d"
    forward_end_column = f"forward_end_{horizon}d"

    working = panel.loc[panel["scoring_complete"]].copy()
    working[forward_end_column] = pd.to_datetime(working[forward_end_column], utc=True)
    working["session_date"] = pd.to_datetime(working["session_date"], utc=True)

    dates = sorted(working["session_date"].dropna().unique())
    candidates = generate_weight_grid()

    fold_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []

    start = MIN_TRAINING_DATES
    fold_number = 0

    while start + TEST_WINDOW_DATES <= len(dates):
        test_dates = dates[start : start + TEST_WINDOW_DATES]
        test_start = pd.Timestamp(test_dates[0])
        test_end = pd.Timestamp(test_dates[-1])

        train = working.loc[
            (working["session_date"] < test_start)
            & (working[forward_end_column] < test_start)
            & working[forward_column].notna()
        ].copy()

        test = working.loc[
            working["session_date"].isin(test_dates)
            & working[forward_column].notna()
        ].copy()

        if train["session_date"].nunique() < MIN_TRAINING_DATES or test.empty:
            start += TEST_WINDOW_DATES
            continue

        scored_candidates: list[dict[str, object]] = []
        for candidate_id, weights in enumerate(candidates):
            metrics = evaluate_candidate(
                train,
                weights,
                forward_column=forward_column,
            )
            row: dict[str, object] = {
                "fold": fold_number,
                "candidate_id": candidate_id,
                **weights,
                **metrics,
            }
            scored_candidates.append(row)

        candidate_frame = pd.DataFrame(scored_candidates)
        candidate_frame = candidate_frame.sort_values(
            ["objective", "mean_rank_ic", "mean_top_bottom_spread"],
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)

        best = candidate_frame.iloc[0]
        best_weights = {group: float(best[group]) for group in GROUPS}

        test_metrics = evaluate_candidate(
            test,
            best_weights,
            forward_column=forward_column,
        )

        fold_rows.append(
            {
                "fold": fold_number,
                "train_dates": int(train["session_date"].nunique()),
                "test_dates": int(test["session_date"].nunique()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                **{f"weight_{group}": best_weights[group] for group in GROUPS},
                **{f"train_{key}": value for key, value in best.items() if key in {
                    "mean_rank_ic",
                    "median_rank_ic",
                    "mean_top_bottom_spread",
                    "positive_spread_rate",
                    "mean_turnover",
                    "objective",
                }},
                **{f"test_{key}": value for key, value in test_metrics.items()},
            }
        )

        candidate_frame["test_start"] = str(test_start.date())
        candidate_frame["test_end"] = str(test_end.date())
        candidate_rows.extend(candidate_frame.to_dict(orient="records"))

        fold_number += 1
        start += TEST_WINDOW_DATES

    if not fold_rows:
        raise ValueError("No eligible walk-forward folds were produced")

    return (
        pd.DataFrame(fold_rows),
        pd.DataFrame(candidate_rows),
    )
