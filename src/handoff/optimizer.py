from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from config.scanner_handoff import (
    CANDIDATE_COLUMNS,
    DEFAULT_CANDIDATE_LIMIT,
    EXPECTED_ALPHA_SPEC_VERSION,
    EXPECTED_PROVIDER,
    HANDOFF_CONTRACT_VERSION,
    PRIMARY_SIGNAL_NAME,
    SELECTION_POLICY,
)
from src.utils.hashing import sha256_file, stable_dataframe_hash


_REQUIRED_ALPHA_COLUMNS = (
    "timestamp",
    "symbol",
    "close",
    PRIMARY_SIGNAL_NAME,
    "ema_50_to_200",
    "alpha_score",
    "alpha_rank",
    "alpha_percentile",
    "alpha_complete",
    "alpha_spec_version",
)


def _read_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return dict(value)


def _require_sha256(value: Any, *, field_name: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64:
        raise ValueError(f"{field_name} must be a 64-character SHA-256 digest")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be lowercase hexadecimal") from exc
    return normalized


def _coerce_bool(series: pd.Series, *, field_name: str) -> pd.Series:
    mapping = {
        True: True,
        False: False,
        1: True,
        0: False,
        "true": True,
        "false": False,
        "True": True,
        "False": False,
        "1": True,
        "0": False,
    }
    result = series.map(mapping)
    if result.isna().any():
        bad = sorted(series.loc[result.isna()].astype(str).unique().tolist())
        raise ValueError(f"{field_name} contains invalid boolean values: {bad}")
    return result.astype(bool)


def _validate_source_manifest(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "alpha_spec_version",
        "alpha_freeze_date",
        "provider",
        "session_date",
        "rows",
        "alpha_complete_rows",
        "snapshot_sha256",
        "created_at_utc",
        "immutable",
    }
    missing = sorted(required.difference(manifest))
    if missing:
        raise ValueError(f"Alpha manifest missing required fields: {missing}")

    alpha_spec = str(manifest["alpha_spec_version"]).strip()
    provider = str(manifest["provider"]).strip().lower()
    session = str(manifest["session_date"]).strip()
    immutable = manifest["immutable"]

    if alpha_spec != EXPECTED_ALPHA_SPEC_VERSION:
        raise ValueError(
            f"Expected alpha spec {EXPECTED_ALPHA_SPEC_VERSION!r}; got {alpha_spec!r}"
        )
    if provider != EXPECTED_PROVIDER:
        raise ValueError(
            f"Expected provider {EXPECTED_PROVIDER!r}; got {provider!r}"
        )
    if immutable is not True:
        raise ValueError("Source alpha manifest must declare immutable=true")

    parsed_session = pd.Timestamp(session)
    if parsed_session.strftime("%Y-%m-%d") != session:
        raise ValueError("Source alpha manifest session_date must use YYYY-MM-DD")

    created_at = pd.to_datetime(manifest["created_at_utc"], errors="coerce", utc=True)
    if pd.isna(created_at):
        raise ValueError("Source alpha manifest created_at_utc is invalid")

    return {
        **dict(manifest),
        "alpha_spec_version": alpha_spec,
        "provider": provider,
        "session_date": session,
        "snapshot_sha256": _require_sha256(
            manifest["snapshot_sha256"],
            field_name="snapshot_sha256",
        ),
    }


def _validate_alpha_ranking(
    frame: pd.DataFrame,
    *,
    manifest: Mapping[str, Any],
) -> pd.DataFrame:
    missing = [column for column in _REQUIRED_ALPHA_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Alpha ranking missing required columns: {missing}")
    if frame.empty:
        raise ValueError("Alpha ranking is empty")

    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce", utc=True)
    if result["timestamp"].isna().any():
        raise ValueError("Alpha ranking contains invalid timestamps")

    sessions = sorted(set(result["timestamp"].dt.date))
    expected_session = pd.Timestamp(manifest["session_date"]).date()
    if sessions != [expected_session]:
        raise ValueError(
            "Alpha ranking session does not match source manifest: "
            f"ranking={sessions}, manifest={expected_session}"
        )

    if len(result) != int(manifest["rows"]):
        raise ValueError("Alpha ranking row count does not match source manifest")

    result["alpha_complete"] = _coerce_bool(
        result["alpha_complete"],
        field_name="alpha_complete",
    )

    if int(result["alpha_complete"].sum()) != int(manifest["alpha_complete_rows"]):
        raise ValueError(
            "Alpha-complete row count does not match source manifest"
        )

    specs = set(result["alpha_spec_version"].astype(str).str.strip())
    if specs != {manifest["alpha_spec_version"]}:
        raise ValueError(
            "Alpha ranking alpha_spec_version does not match source manifest"
        )

    if result["symbol"].astype(str).str.strip().eq("").any():
        raise ValueError("Alpha ranking contains blank symbols")
    if result["symbol"].astype(str).str.upper().duplicated().any():
        raise ValueError("Alpha ranking contains duplicate symbols")

    actual_snapshot_hash = stable_dataframe_hash(frame)
    expected_snapshot_hash = str(manifest["snapshot_sha256"]).lower()
    if actual_snapshot_hash != expected_snapshot_hash:
        raise ValueError(
            "Alpha ranking no longer matches immutable source manifest "
            f"(expected {expected_snapshot_hash}, got {actual_snapshot_hash})"
        )

    return result


def _validate_candidate_limit(candidate_limit: int) -> int:
    try:
        value = int(candidate_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_limit must be an integer") from exc
    if value <= 0:
        raise ValueError("candidate_limit must be positive")
    return value


def build_candidate_handoff(
    *,
    alpha_ranking_path: Path,
    alpha_manifest_path: Path,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    generated_at_utc: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    candidate_limit = _validate_candidate_limit(candidate_limit)
    alpha_ranking_path = Path(alpha_ranking_path)
    alpha_manifest_path = Path(alpha_manifest_path)

    source_manifest = _validate_source_manifest(_read_json(alpha_manifest_path))
    source = pd.read_csv(alpha_ranking_path, low_memory=False)
    source = _validate_alpha_ranking(source, manifest=source_manifest)

    eligible = source.loc[source["alpha_complete"]].copy()
    if eligible.empty:
        raise ValueError("Source alpha ranking contains no eligible rows")

    numeric_columns = (
        "alpha_rank",
        "alpha_score",
        "alpha_percentile",
        "close",
        PRIMARY_SIGNAL_NAME,
        "ema_50_to_200",
    )
    for column in numeric_columns:
        eligible[column] = pd.to_numeric(eligible[column], errors="coerce")
        if eligible[column].isna().any():
            raise ValueError(f"Eligible alpha rows contain non-numeric {column}")
        if not np.isfinite(eligible[column].to_numpy(dtype=float)).all():
            raise ValueError(f"Eligible alpha rows contain non-finite {column}")

    ranks = eligible["alpha_rank"].to_numpy(dtype=float)
    if not np.all(np.equal(ranks, np.floor(ranks))):
        raise ValueError("Eligible alpha ranks must be integers")
    if len(set(ranks.astype(int))) != len(ranks):
        raise ValueError("Eligible alpha ranks must be unique")

    eligible = eligible.sort_values(
        ["alpha_rank", "symbol"],
        ascending=[True, True],
        kind="stable",
    )
    selected = eligible.head(candidate_limit).copy()

    selected_ranks = selected["alpha_rank"].astype(int).tolist()
    expected_ranks = list(range(1, len(selected) + 1))
    if selected_ranks != expected_ranks:
        raise ValueError(
            "Selected candidates must be the contiguous top-ranked set "
            f"{expected_ranks}; got {selected_ranks}"
        )

    if not selected["alpha_percentile"].between(0.0, 100.0, inclusive="both").all():
        raise ValueError("scanner percentiles must be between 0 and 100")
    if not selected["close"].gt(0.0).all():
        raise ValueError("candidate close values must be positive")

    if generated_at_utc is None:
        generated_at = datetime.now(timezone.utc)
    else:
        generated_at = pd.to_datetime(generated_at_utc, errors="coerce", utc=True)
        if pd.isna(generated_at):
            raise ValueError("generated_at_utc is invalid")
        generated_at = generated_at.to_pydatetime()

    generated_text = generated_at.isoformat()
    source_manifest_sha256 = sha256_file(alpha_manifest_path)

    rows: list[dict[str, Any]] = []
    for record in selected.to_dict(orient="records"):
        source_timestamp = pd.Timestamp(record["timestamp"])
        if source_timestamp.tzinfo is None:
            source_timestamp = source_timestamp.tz_localize("UTC")
        else:
            source_timestamp = source_timestamp.tz_convert("UTC")

        rows.append(
            {
                "handoff_contract_version": HANDOFF_CONTRACT_VERSION,
                "scanner_alpha_spec_version": source_manifest["alpha_spec_version"],
                "scanner_provider": source_manifest["provider"],
                "as_of_session": source_manifest["session_date"],
                "generated_at_utc": generated_text,
                "scanner_snapshot_sha256": source_manifest["snapshot_sha256"],
                "source_alpha_manifest_sha256": source_manifest_sha256,
                "source_timestamp_utc": source_timestamp.isoformat(),
                "symbol": str(record["symbol"]).strip().upper(),
                "scanner_rank": int(record["alpha_rank"]),
                "scanner_score": float(record["alpha_score"]),
                "scanner_percentile": float(record["alpha_percentile"]),
                "scanner_eligible": True,
                "close": float(record["close"]),
                "primary_signal_name": PRIMARY_SIGNAL_NAME,
                "primary_signal_value": float(record[PRIMARY_SIGNAL_NAME]),
                "ema_50_to_200": float(record["ema_50_to_200"]),
            }
        )

    candidates = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)

    manifest = {
        "handoff_contract_version": HANDOFF_CONTRACT_VERSION,
        "scanner_alpha_spec_version": source_manifest["alpha_spec_version"],
        "scanner_provider": source_manifest["provider"],
        "as_of_session": source_manifest["session_date"],
        "generated_at_utc": generated_text,
        "scanner_snapshot_sha256": source_manifest["snapshot_sha256"],
        "source_alpha_manifest_sha256": source_manifest_sha256,
        "candidate_count": int(len(candidates)),
        "candidate_limit": candidate_limit,
        "selection_policy": SELECTION_POLICY,
        "candidate_csv_sha256": "",
        "immutable": True,
        "source_alpha_ranking": str(alpha_ranking_path),
        "source_alpha_manifest": str(alpha_manifest_path),
    }

    return candidates, manifest


def write_candidate_handoff(
    *,
    alpha_ranking_path: Path,
    alpha_manifest_path: Path,
    output_dir: Path,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    generated_at_utc: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    candidates, manifest = build_candidate_handoff(
        alpha_ranking_path=alpha_ranking_path,
        alpha_manifest_path=alpha_manifest_path,
        candidate_limit=candidate_limit,
        generated_at_utc=generated_at_utc,
    )

    output_dir = Path(output_dir)
    candidate_csv = output_dir / "scanner_candidates.csv"
    candidate_manifest = output_dir / "scanner_candidates_manifest.json"

    if candidate_csv.exists() or candidate_manifest.exists():
        raise FileExistsError(
            f"Candidate handoff already exists in {output_dir}; refusing to overwrite"
        )

    output_dir.mkdir(parents=True, exist_ok=False)
    candidates.to_csv(candidate_csv, index=False, lineterminator="\n")

    manifest = {
        **manifest,
        "candidate_csv_sha256": sha256_file(candidate_csv),
    }
    candidate_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return candidate_csv, candidate_manifest, manifest
