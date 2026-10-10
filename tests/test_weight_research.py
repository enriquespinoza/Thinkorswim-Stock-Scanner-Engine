import numpy as np
import pandas as pd

from config.scoring import FEATURE_GROUPS
from src.scoring.weight_research import (
    GROUPS,
    add_composite_score,
    evaluate_candidate,
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
