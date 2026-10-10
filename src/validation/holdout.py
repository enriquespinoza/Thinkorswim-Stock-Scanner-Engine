from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from config.alpha import ALPHA_FREEZE_DATE, ALPHA_SPEC_VERSION
from src.utils.hashing import stable_dataframe_hash


def assert_true_holdout_session(session_date: date) -> None:
    freeze = date.fromisoformat(ALPHA_FREEZE_DATE)
    if session_date <= freeze:
        raise ValueError(
            f"Holdout session {session_date} is not after alpha freeze date {freeze}"
        )


def validate_common_session(snapshot: pd.DataFrame) -> date:
    if snapshot.empty:
        raise ValueError("Holdout alpha snapshot is empty")

    timestamps = pd.to_datetime(snapshot["timestamp"], utc=True)
    sessions = sorted(set(timestamps.dt.date))
    if len(sessions) != 1:
        raise ValueError(
            "Holdout snapshot must use exactly one common market session; "
            f"found {sessions}"
        )

    session = sessions[0]
    assert_true_holdout_session(session)
    return session


def write_immutable_holdout_snapshot(
    snapshot: pd.DataFrame,
    *,
    provider: str,
    output_root: Path,
) -> tuple[Path, Path, str]:
    session = validate_common_session(snapshot)
    digest = stable_dataframe_hash(snapshot)

    session_dir = output_root / ALPHA_SPEC_VERSION / session.isoformat()
    snapshot_path = session_dir / "alpha_ranking.csv"
    manifest_path = session_dir / "manifest.json"

    if snapshot_path.exists() or manifest_path.exists():
        raise FileExistsError(
            f"Holdout snapshot already exists for {session}; refusing to overwrite"
        )

    session_dir.mkdir(parents=True, exist_ok=False)
    snapshot.to_csv(snapshot_path, index=False)

    manifest = {
        "alpha_spec_version": ALPHA_SPEC_VERSION,
        "alpha_freeze_date": ALPHA_FREEZE_DATE,
        "provider": provider,
        "session_date": session.isoformat(),
        "rows": int(len(snapshot)),
        "alpha_complete_rows": int(snapshot["alpha_complete"].sum()),
        "snapshot_sha256": digest,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "immutable": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot_path, manifest_path, digest
