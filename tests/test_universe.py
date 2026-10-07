import pandas as pd

from src.universe.builder import build_universe_frame
from src.universe.models import UniverseSecurity
from src.universe.providers import StaticUniverseProvider, to_yfinance_symbol
from src.utils.hashing import stable_dataframe_hash


def test_yfinance_symbol_normalization() -> None:
    assert to_yfinance_symbol("BRK.B") == "BRK-B"
    assert to_yfinance_symbol(" aapl ") == "AAPL"


def test_universe_build_is_sorted_and_deterministic() -> None:
    provider = StaticUniverseProvider(
        [
            UniverseSecurity("MSFT", "MSFT", "Microsoft", "Technology"),
            UniverseSecurity("AAPL", "AAPL", "Apple", "Technology"),
        ]
    )
    frame = build_universe_frame(provider)
    assert frame["symbol"].tolist() == ["AAPL", "MSFT"]
    assert stable_dataframe_hash(frame) == stable_dataframe_hash(frame.sample(frac=1, random_state=7))


def test_duplicate_symbol_rejected() -> None:
    provider = StaticUniverseProvider(
        [
            UniverseSecurity("AAPL", "AAPL", "Apple"),
            UniverseSecurity("AAPL", "AAPL", "Apple duplicate"),
        ]
    )
    try:
        build_universe_frame(provider)
    except ValueError as exc:
        assert "Duplicate universe symbols" in str(exc)
    else:
        raise AssertionError("duplicate symbol should have raised")
