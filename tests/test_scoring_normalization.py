import numpy as np
import pandas as pd

from config.scoring import SCORING_FEATURES
from src.scoring.normalization import normalize_scoring_snapshot


def _snapshot(rows: int = 100) -> pd.DataFrame:
    data = {
        "symbol": [f"S{i:03d}" for i in range(rows)],
    }
    for idx, feature in enumerate(SCORING_FEATURES, start=1):
        data[feature] = np.arange(rows, dtype=float) + idx
    return pd.DataFrame(data)


def test_normalization_adds_oriented_zscores_and_missing_flags() -> None:
    frame = _snapshot()
    result = normalize_scoring_snapshot(frame)

    for feature in SCORING_FEATURES:
        assert f"z_{feature}" in result.columns
        assert f"missing_{feature}" in result.columns

    assert result["scoring_missing_count"].eq(0).all()
    assert result["scoring_complete"].all()


def test_missing_values_are_not_imputed() -> None:
    frame = _snapshot()
    feature = SCORING_FEATURES[0]
    frame.loc[0, feature] = np.nan

    result = normalize_scoring_snapshot(frame)

    assert pd.isna(result.loc[0, f"z_{feature}"])
    assert bool(result.loc[0, f"missing_{feature}"]) is True
    assert result.loc[0, "scoring_missing_count"] == 1
    assert bool(result.loc[0, "scoring_complete"]) is False


def test_phase3a_does_not_create_score_or_rank() -> None:
    result = normalize_scoring_snapshot(_snapshot())

    forbidden = {"score", "composite_score", "rank", "scanner_rank"}
    assert forbidden.isdisjoint(result.columns)


def test_lower_risk_maps_to_higher_oriented_signal() -> None:
    frame = _snapshot()
    result = normalize_scoring_snapshot(frame)

    feature = "volatility_20d"
    assert result.loc[0, f"z_{feature}"] > result.loc[len(result) - 1, f"z_{feature}"]


def test_higher_momentum_maps_to_higher_oriented_signal() -> None:
    frame = _snapshot()
    result = normalize_scoring_snapshot(frame)

    feature = "return_60d"
    assert result.loc[len(result) - 1, f"z_{feature}"] > result.loc[0, f"z_{feature}"]
