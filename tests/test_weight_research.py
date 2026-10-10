import numpy as np
import pandas as pd

from config.scoring import FEATURE_GROUPS
from src.scoring.weight_research import (
    GROUPS,
    add_composite_score,
    evaluate_candidate,
    evaluate_candidate_grid_daily,
    generate_weight_grid,
)


def test_weight_grid_sums_to_one() -> None:
    grid = generate_weight_grid(step=0.10)

    assert len(grid) == 1001
    for weights in grid:
        assert set(weights) == set(FEATURE_GROUPS)
        assert np.isclose(sum(weights.values()), 1.0)
        assert all(weight >= 0.0 for weight in weights.values())


def test_composite_score_uses_only_group_weights() -> None:
    frame = pd.DataFrame(
        {
            "group_momentum": [1.0, 2.0],
            "group_trend": [0.0, 0.0],
            "group_relative_strength": [0.0, 0.0],
            "group_risk": [0.0, 0.0],
            "group_participation": [0.0, 0.0],
        }
    )
    weights = {group: 0.0 for group in GROUPS}
    weights["momentum"] = 1.0

    result = add_composite_score(frame, weights)

    assert result["research_score"].tolist() == [1.0, 2.0]


def test_candidate_evaluation_rewards_predictive_score() -> None:
    rows = []
    for date_index, date in enumerate(pd.date_range("2026-01-02", periods=4, freq="W-FRI", tz="UTC")):
        for idx in range(100):
            signal = float(idx)
            rows.append(
                {
                    "session_date": date,
                    "symbol": f"S{idx:03d}",
                    "group_momentum": signal,
                    "group_trend": 0.0,
                    "group_relative_strength": 0.0,
                    "group_risk": 0.0,
                    "group_participation": 0.0,
                    "forward_return_20d": signal / 1000.0,
                }
            )

    frame = pd.DataFrame(rows)
    weights = {group: 0.0 for group in GROUPS}
    weights["momentum"] = 1.0

    result = evaluate_candidate(
        frame,
        weights,
        forward_column="forward_return_20d",
    )

    assert result["mean_rank_ic"] > 0.99
    assert result["mean_top_bottom_spread"] > 0.0
    assert result["positive_spread_rate"] == 1.0


def test_rank_ic_handles_ties_without_scipy() -> None:
    rows = []
    date = pd.Timestamp("2026-01-02", tz="UTC")
    for idx in range(100):
        signal = float(idx // 10)
        rows.append(
            {
                "session_date": date,
                "symbol": f"S{idx:03d}",
                "group_momentum": signal,
                "group_trend": 0.0,
                "group_relative_strength": 0.0,
                "group_risk": 0.0,
                "group_participation": 0.0,
                "forward_return_20d": signal / 100.0,
            }
        )

    frame = pd.DataFrame(rows)
    weights = {group: 0.0 for group in GROUPS}
    weights["momentum"] = 1.0

    result = evaluate_candidate(
        frame,
        weights,
        forward_column="forward_return_20d",
    )

    assert result["mean_rank_ic"] > 0.99


def test_vectorized_grid_matches_single_candidate_metrics() -> None:
    rows = []
    dates = pd.date_range("2026-01-02", periods=4, freq="W-FRI", tz="UTC")

    for date_index, date in enumerate(dates):
        for idx in range(100):
            signal = float(idx)
            rows.append(
                {
                    "session_date": date,
                    "symbol": f"S{idx:03d}",
                    "group_momentum": signal,
                    "group_trend": signal * 0.25,
                    "group_relative_strength": signal * 0.50,
                    "group_risk": -signal * 0.10,
                    "group_participation": signal * 0.05,
                    "forward_return_20d": signal / 1000.0,
                    "forward_end_20d": date + pd.Timedelta(days=28),
                }
            )

    frame = pd.DataFrame(rows)

    weights = {group: 0.0 for group in GROUPS}
    weights["momentum"] = 0.6
    weights["relative_strength"] = 0.4

    single = evaluate_candidate(
        frame,
        weights,
        forward_column="forward_return_20d",
    )

    daily = evaluate_candidate_grid_daily(
        frame,
        [weights],
        forward_column="forward_return_20d",
        forward_end_column="forward_end_20d",
    )

    vectorized = {
        "mean_rank_ic": float(daily["rank_ic"].mean()),
        "median_rank_ic": float(daily["rank_ic"].median()),
        "mean_top_bottom_spread": float(daily["top_bottom_spread"].mean()),
        "positive_spread_rate": float(
            (daily["top_bottom_spread"] > 0.0).mean()
        ),
        "mean_turnover": float(daily["turnover"].mean(skipna=True)),
    }

    for key, value in vectorized.items():
        assert np.isclose(value, single[key], equal_nan=True)
