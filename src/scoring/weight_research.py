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
GROUP_COLUMNS = tuple(f"group_{group}" for group in GROUPS)


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
        valid = cross_section.dropna(
            subset=["research_score", forward_column]
        )
        if len(valid) < 50:
            continue

        score_rank = valid["research_score"].rank(method="average")
        forward_rank = valid[forward_column].rank(method="average")
        ic = score_rank.corr(forward_rank)

        valid_sorted = valid.sort_values(
            ["research_score", "symbol"],
            ascending=[False, True],
            kind="stable",
        )
        basket_size = max(1, int(len(valid_sorted) * TOP_QUANTILE))
        bottom_size = max(1, int(len(valid_sorted) * BOTTOM_QUANTILE))

        top = valid_sorted.head(basket_size)
        bottom = valid_sorted.tail(bottom_size)
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
        return _empty_metrics()

    return _aggregate_single_candidate(daily)


def _empty_metrics() -> dict[str, float]:
    return {
        "mean_rank_ic": np.nan,
        "median_rank_ic": np.nan,
        "mean_top_bottom_spread": np.nan,
        "positive_spread_rate": np.nan,
        "mean_turnover": np.nan,
        "objective": np.nan,
    }


def _aggregate_single_candidate(daily: pd.DataFrame) -> dict[str, float]:
    if daily.empty:
        return _empty_metrics()

    mean_ic = float(daily["rank_ic"].mean())
    mean_turnover = float(daily["turnover"].mean(skipna=True))

    return {
        "mean_rank_ic": mean_ic,
        "median_rank_ic": float(daily["rank_ic"].median()),
        "mean_top_bottom_spread": float(daily["top_bottom_spread"].mean()),
        "positive_spread_rate": float(
            (daily["top_bottom_spread"] > 0.0).mean()
        ),
        "mean_turnover": mean_turnover,
        "objective": mean_ic - TURNOVER_PENALTY * mean_turnover,
    }


def _candidate_weight_frame(
    candidates: list[dict[str, float]],
) -> pd.DataFrame:
    frame = pd.DataFrame(candidates)
    frame.insert(0, "candidate_id", np.arange(len(frame), dtype=int))
    return frame


def _candidate_weight_matrix(
    candidates: list[dict[str, float]],
) -> np.ndarray:
    return np.asarray(
        [[float(candidate[group]) for group in GROUPS] for candidate in candidates],
        dtype=float,
    )


def _rank_columns(values: np.ndarray) -> np.ndarray:
    return (
        pd.DataFrame(values)
        .rank(axis=0, method="average")
        .to_numpy(dtype=float)
    )


def evaluate_candidate_grid_daily(
    frame: pd.DataFrame,
    candidates: list[dict[str, float]],
    *,
    forward_column: str,
    forward_end_column: str,
    progress: bool = False,
) -> pd.DataFrame:
    """Evaluate every candidate once per scoring date.

    This is mathematically equivalent to repeatedly calling evaluate_candidate,
    but avoids copying/grouping the full panel once for every candidate.
    """
    if not candidates:
        raise ValueError("Candidate weight grid cannot be empty")

    required = {
        "session_date",
        "symbol",
        forward_column,
        forward_end_column,
        *GROUP_COLUMNS,
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Candidate evaluation frame missing columns: {missing}")

    weights = _candidate_weight_matrix(candidates)
    candidate_ids = np.arange(len(candidates), dtype=int)

    symbol_values = sorted(frame["symbol"].astype(str).unique())
    symbol_codes = {symbol: idx for idx, symbol in enumerate(symbol_values)}
    candidate_axis = np.arange(len(candidates), dtype=int)

    grouped = list(frame.groupby("session_date", sort=True))
    total_dates = len(grouped)
    previous_membership: np.ndarray | None = None
    rows: list[pd.DataFrame] = []

    for date_index, (session_date, cross_section) in enumerate(grouped, start=1):
        valid = cross_section.dropna(
            subset=[*GROUP_COLUMNS, forward_column, forward_end_column]
        )
        if len(valid) < 50:
            continue

        x = valid.loc[:, GROUP_COLUMNS].to_numpy(dtype=float)
        y = valid[forward_column].to_numpy(dtype=float)

        # n_symbols x n_candidates
        scores = x @ weights.T

        score_ranks = _rank_columns(scores)
        forward_rank = (
            valid[forward_column]
            .rank(method="average")
            .to_numpy(dtype=float)
        )

        centered_scores = score_ranks - score_ranks.mean(axis=0, keepdims=True)
        centered_forward = forward_rank - forward_rank.mean()

        numerator = centered_forward @ centered_scores
        denominator = np.sqrt(
            np.sum(centered_forward**2)
            * np.sum(centered_scores**2, axis=0)
        )
        rank_ic = np.divide(
            numerator,
            denominator,
            out=np.full(len(candidates), np.nan, dtype=float),
            where=denominator > 0.0,
        )

        order = np.argsort(scores, axis=0, kind="stable")
        basket_size = max(1, int(len(valid) * TOP_QUANTILE))
        bottom_size = max(1, int(len(valid) * BOTTOM_QUANTILE))

        bottom_idx = order[:bottom_size, :]
        top_idx = order[-basket_size:, :]

        top_returns = y[top_idx]
        bottom_returns = y[bottom_idx]
        spread = top_returns.mean(axis=0) - bottom_returns.mean(axis=0)

        codes = np.fromiter(
            (symbol_codes[str(value)] for value in valid["symbol"]),
            dtype=int,
            count=len(valid),
        )
        top_codes = codes[top_idx]

        membership = np.zeros(
            (len(symbol_values), len(candidates)),
            dtype=bool,
        )
        membership[
            top_codes,
            np.broadcast_to(candidate_axis, top_codes.shape),
        ] = True

        turnover = np.full(len(candidates), np.nan, dtype=float)
        if previous_membership is not None:
            overlap = np.logical_and(
                membership,
                previous_membership,
            ).sum(axis=0)
            current_size = membership.sum(axis=0)
            turnover = 1.0 - np.divide(
                overlap,
                current_size,
                out=np.zeros(len(candidates), dtype=float),
                where=current_size > 0,
            )
        previous_membership = membership

        label_end = pd.to_datetime(
            valid[forward_end_column],
            utc=True,
        ).max()

        rows.append(
            pd.DataFrame(
                {
                    "session_date": session_date,
                    "label_end": label_end,
                    "candidate_id": candidate_ids,
                    "rank_ic": rank_ic,
                    "top_bottom_spread": spread,
                    "turnover": turnover,
                }
            )
        )

        if progress and (
            date_index == total_dates
            or date_index % 25 == 0
        ):
            print(
                "Candidate-grid evaluation: "
                f"{date_index}/{total_dates} scoring dates"
            )

    if not rows:
        raise ValueError("No valid daily candidate evaluations were produced")

    return pd.concat(rows, ignore_index=True)


def _aggregate_candidate_grid(
    daily: pd.DataFrame,
    *,
    reset_first_turnover: bool = False,
) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(
            columns=[
                "candidate_id",
                "mean_rank_ic",
                "median_rank_ic",
                "mean_top_bottom_spread",
                "positive_spread_rate",
                "mean_turnover",
                "objective",
            ]
        )

    working = daily.copy()

    if reset_first_turnover:
        first_date = working["session_date"].min()
        working.loc[
            working["session_date"].eq(first_date),
            "turnover",
        ] = np.nan

    grouped = working.groupby("candidate_id", sort=True)

    result = grouped.agg(
        mean_rank_ic=("rank_ic", "mean"),
        median_rank_ic=("rank_ic", "median"),
        mean_top_bottom_spread=("top_bottom_spread", "mean"),
        mean_turnover=("turnover", "mean"),
    ).reset_index()

    positive = (
        working.assign(
            positive_spread=working["top_bottom_spread"].gt(0.0)
        )
        .groupby("candidate_id", sort=True)["positive_spread"]
        .mean()
        .rename("positive_spread_rate")
        .reset_index()
    )
    result = result.merge(positive, on="candidate_id", how="left")

    result["objective"] = (
        result["mean_rank_ic"]
        - TURNOVER_PENALTY * result["mean_turnover"]
    )
    return result


def walk_forward_weight_research(
    panel: pd.DataFrame,
    *,
    progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    horizon = PRIMARY_FORWARD_RETURN_HORIZON
    forward_column = f"forward_return_{horizon}d"
    forward_end_column = f"forward_end_{horizon}d"

    working = panel.loc[panel["scoring_complete"]].copy()
    working[forward_end_column] = pd.to_datetime(
        working[forward_end_column],
        utc=True,
    )
    working["session_date"] = pd.to_datetime(
        working["session_date"],
        utc=True,
    )

    candidates = generate_weight_grid()
    weights_frame = _candidate_weight_frame(candidates)

    if progress:
        print(
            f"Evaluating {len(candidates)} candidate weight vectors "
            "across historical scoring dates..."
        )

    daily_grid = evaluate_candidate_grid_daily(
        working,
        candidates,
        forward_column=forward_column,
        forward_end_column=forward_end_column,
        progress=progress,
    )

    dates = sorted(daily_grid["session_date"].dropna().unique())

    fold_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []

    start = MIN_TRAINING_DATES
    fold_number = 0

    while start + TEST_WINDOW_DATES <= len(dates):
        test_dates = dates[start : start + TEST_WINDOW_DATES]
        test_start = pd.Timestamp(test_dates[0])
        test_end = pd.Timestamp(test_dates[-1])

        # Date-level embargo: the full cross-section's forward-label window must
        # end before the first test date. This is slightly stricter than row-level
        # filtering and prevents partial-date leakage.
        train_daily = daily_grid.loc[
            (daily_grid["session_date"] < test_start)
            & (daily_grid["label_end"] < test_start)
        ].copy()

        test_daily = daily_grid.loc[
            daily_grid["session_date"].isin(test_dates)
        ].copy()

        train_date_count = train_daily["session_date"].nunique()
        test_date_count = test_daily["session_date"].nunique()

        if train_date_count < MIN_TRAINING_DATES or test_daily.empty:
            start += TEST_WINDOW_DATES
            continue

        train_metrics = _aggregate_candidate_grid(train_daily)
        candidate_frame = weights_frame.merge(
            train_metrics,
            on="candidate_id",
            how="left",
        )
        candidate_frame = candidate_frame.sort_values(
            ["objective", "mean_rank_ic", "mean_top_bottom_spread"],
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)

        best = candidate_frame.iloc[0]
        best_id = int(best["candidate_id"])
        best_weights = {
            group: float(best[group])
            for group in GROUPS
        }

        best_test_daily = test_daily.loc[
            test_daily["candidate_id"].eq(best_id)
        ]
        test_metrics_frame = _aggregate_candidate_grid(
            best_test_daily,
            reset_first_turnover=True,
        )
        if test_metrics_frame.empty:
            test_metrics = _empty_metrics()
        else:
            test_record = test_metrics_frame.iloc[0]
            test_metrics = {
                key: float(test_record[key])
                for key in (
                    "mean_rank_ic",
                    "median_rank_ic",
                    "mean_top_bottom_spread",
                    "positive_spread_rate",
                    "mean_turnover",
                    "objective",
                )
            }

        fold_rows.append(
            {
                "fold": fold_number,
                "train_dates": int(train_date_count),
                "test_dates": int(test_date_count),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                **{
                    f"weight_{group}": best_weights[group]
                    for group in GROUPS
                },
                **{
                    f"train_{key}": float(best[key])
                    for key in (
                        "mean_rank_ic",
                        "median_rank_ic",
                        "mean_top_bottom_spread",
                        "positive_spread_rate",
                        "mean_turnover",
                        "objective",
                    )
                },
                **{
                    f"test_{key}": value
                    for key, value in test_metrics.items()
                },
            }
        )

        candidate_frame["fold"] = fold_number
        candidate_frame["test_start"] = str(test_start.date())
        candidate_frame["test_end"] = str(test_end.date())
        candidate_rows.extend(candidate_frame.to_dict(orient="records"))

        if progress:
            print(
                f"Walk-forward fold {fold_number}: "
                f"train={train_date_count} dates, "
                f"test={test_date_count} dates, "
                f"best candidate={best_id}"
            )

        fold_number += 1
        start += TEST_WINDOW_DATES

    if not fold_rows:
        raise ValueError("No eligible walk-forward folds were produced")

    return (
        pd.DataFrame(fold_rows),
        pd.DataFrame(candidate_rows),
    )
