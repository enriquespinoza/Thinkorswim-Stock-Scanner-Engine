from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    path = Path(path)
    return sha256_bytes(path.read_bytes())


def stable_dataframe_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    normalized = normalized.sort_values(list(normalized.columns), kind="mergesort")
    normalized = normalized.reset_index(drop=True)
    csv_bytes = normalized.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return sha256_bytes(csv_bytes)
