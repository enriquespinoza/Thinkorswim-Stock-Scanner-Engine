import pandas as pd

from src.data.provider_artifacts import canonical_json_bytes, save_raw_json


def test_canonical_json_is_order_independent() -> None:
    left = canonical_json_bytes({"b": 2, "a": 1})
    right = canonical_json_bytes({"a": 1, "b": 2})
    assert left == right


def test_raw_json_hash_is_deterministic(tmp_path) -> None:
    left = save_raw_json({"b": 2, "a": 1}, tmp_path / "left.json")
    right = save_raw_json({"a": 1, "b": 2}, tmp_path / "right.json")
    assert left == right
