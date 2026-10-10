import pytest

from src.universe.symbols import to_schwab_symbol, to_yahoo_symbol


@pytest.mark.parametrize(
    ("canonical", "yahoo", "schwab"),
    [
        ("AAPL", "AAPL", "AAPL"),
        ("BRK.B", "BRK-B", "BRK/B"),
        ("BF.B", "BF-B", "BF/B"),
    ],
)
def test_provider_specific_symbol_mapping(
    canonical: str,
    yahoo: str,
    schwab: str,
) -> None:
    assert to_yahoo_symbol(canonical) == yahoo
    assert to_schwab_symbol(canonical) == schwab
