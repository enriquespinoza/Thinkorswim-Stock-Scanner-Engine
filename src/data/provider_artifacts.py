from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.hashing import sha256_bytes, stable_dataframe_hash


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def save_raw_json(payload: dict[str, Any], path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(payload)
    path.write_bytes(encoded)
    return sha256_bytes(encoded)


def save_normalized_bars(frame: pd.DataFrame, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return stable_dataframe_hash(frame)
