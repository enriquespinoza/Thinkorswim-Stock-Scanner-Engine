from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config.alpha import ALPHA_SPEC_VERSION
from src.scoring.alpha import (
    compute_momentum_252d_ex_20d,
    score_alpha_snapshot,
)
from src.validation.holdout import (
    assert_true_holdout_session,
    write_immutable_holdout_snapshot,
)


def _snapshot(rows: int = 100, session: str = "2026-10-12") -> pd.DataFrame:
    idx = np.arange(rows, dtype=float)
    return pd.DataFrame(
        {
            "timestamp": pd.Timestamp(session, tz="UTC"),
            "symbol": [f"S{i:03d}" for i in range(rows)],
            "close": 100.0 + idx,
            "return_20d": 0.01 + idx / 10000.0,
            "return_252d": 0.10 + idx / 1000.0,
            "ema_50_to_200": idx / 1000.0,
        }
    )


def test_12_minus_1_identity() -> None:
    frame = pd.DataFrame(
        {
            "return_20d": [0.10],
            "return_252d": [0.32],
        }
    )
    result = compute_momentum_252d_ex_20d(frame)
    assert np.isclose(result.iloc[0], 0.20)


def test_alpha_v1_uses_only_frozen_primary_signal() -> None:
    frame = _snapshot()
    scored = score_alpha_snapshot(frame)

    assert scored["alpha_spec_version"].eq(ALPHA_SPEC_VERSION).all()
    assert scored["alpha_complete"].all()
    assert scored.iloc[0]["alpha_rank"] == 1.0

    # Reverse the context-only trend feature. Ranking must not change.
    altered = frame.copy()
    altered["ema_50_to_200"] = altered["ema_50_to_200"].iloc[::-1].to_numpy()
    rescored = score_alpha_snapshot(altered)

    assert scored["symbol"].tolist() == rescored["symbol"].tolist()
    assert np.allclose(scored["alpha_score"], rescored["alpha_score"])


def test_holdout_rejects_pre_freeze_sessions() -> None:
    with pytest.raises(ValueError, match="not after alpha freeze date"):
        assert_true_holdout_session(pd.Timestamp("2026-10-09").date())


def test_holdout_snapshot_is_immutable(tmp_path: Path) -> None:
    scored = score_alpha_snapshot(_snapshot())

    write_immutable_holdout_snapshot(
        scored,
        provider="schwab",
        output_root=tmp_path,
    )

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_immutable_holdout_snapshot(
            scored,
            provider="schwab",
            output_root=tmp_path,
        )
