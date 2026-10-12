from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config.scanner_handoff import (
    CANDIDATE_COLUMNS,
    HANDOFF_CONTRACT_VERSION,
)
from src.handoff.optimizer import write_candidate_handoff
from src.utils.hashing import stable_dataframe_hash


def _write_source(tmp_path: Path) -> tuple[Path, Path]:
    rows = 25
    ranking = pd.DataFrame(
        {
            "timestamp": pd.Timestamp("2026-10-12", tz="UTC"),
            "symbol": [f"S{i:03d}" for i in range(rows)],
            "close": 100.0 + np.arange(rows, dtype=float),
            "momentum_252d_ex_20d": np.linspace(0.40, 0.10, rows),
            "ema_50_to_200": np.linspace(0.20, 0.01, rows),
            "alpha_score": np.linspace(3.0, 0.1, rows),
            "alpha_rank": np.arange(1, rows + 1),
            "alpha_percentile": np.linspace(100.0, 0.0, rows),
            "alpha_complete": True,
            "alpha_spec_version": "scanner-alpha-v1",
        }
    )

    ranking_path = tmp_path / "alpha_ranking.csv"
    manifest_path = tmp_path / "manifest.json"

    ranking.to_csv(ranking_path, index=False)

    manifest = {
        "alpha_spec_version": "scanner-alpha-v1",
        "alpha_freeze_date": "2026-10-09",
        "provider": "schwab",
        "session_date": "2026-10-12",
        "rows": rows,
        "alpha_complete_rows": rows,
        "snapshot_sha256": stable_dataframe_hash(ranking),
        "created_at_utc": "2026-10-12T21:00:00+00:00",
        "immutable": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return ranking_path, manifest_path


def test_export_matches_optimizer_contract(tmp_path: Path) -> None:
    ranking_path, manifest_path = _write_source(tmp_path)
    output_dir = tmp_path / "handoff"

    candidate_csv, candidate_manifest, manifest = write_candidate_handoff(
        alpha_ranking_path=ranking_path,
        alpha_manifest_path=manifest_path,
        output_dir=output_dir,
        candidate_limit=20,
        generated_at_utc="2026-10-12T21:05:00+00:00",
    )

    frame = pd.read_csv(candidate_csv)

    assert tuple(frame.columns) == CANDIDATE_COLUMNS
    assert len(frame) == 20
    assert frame["scanner_rank"].tolist() == list(range(1, 21))
    assert frame["symbol"].tolist() == [f"S{i:03d}" for i in range(20)]
    assert frame["scanner_eligible"].astype(bool).all()
    assert frame["handoff_contract_version"].eq(HANDOFF_CONTRACT_VERSION).all()
    assert manifest["candidate_count"] == 20
    assert manifest["candidate_limit"] == 20
    assert candidate_manifest.is_file()


def test_export_fails_if_source_ranking_changed(tmp_path: Path) -> None:
    ranking_path, manifest_path = _write_source(tmp_path)

    frame = pd.read_csv(ranking_path)
    frame.loc[0, "alpha_score"] = -999.0
    frame.to_csv(ranking_path, index=False)

    with pytest.raises(ValueError, match="no longer matches immutable source manifest"):
        write_candidate_handoff(
            alpha_ranking_path=ranking_path,
            alpha_manifest_path=manifest_path,
            output_dir=tmp_path / "handoff",
        )


def test_export_refuses_overwrite(tmp_path: Path) -> None:
    ranking_path, manifest_path = _write_source(tmp_path)
    output_dir = tmp_path / "handoff"

    write_candidate_handoff(
        alpha_ranking_path=ranking_path,
        alpha_manifest_path=manifest_path,
        output_dir=output_dir,
    )

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_candidate_handoff(
            alpha_ranking_path=ranking_path,
            alpha_manifest_path=manifest_path,
            output_dir=output_dir,
        )
