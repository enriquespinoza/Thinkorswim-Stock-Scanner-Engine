from __future__ import annotations


def to_yahoo_symbol(symbol: str) -> str:
    """Map a canonical equity symbol to Yahoo Finance convention."""
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be empty")
    return normalized.replace(".", "-")


def to_schwab_symbol(symbol: str) -> str:
    """Map a canonical equity class-share symbol to Schwab convention.

    Examples:
        BRK.B -> BRK/B
        BF.B  -> BF/B
        AAPL  -> AAPL
    """
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be empty")
    return normalized.replace(".", "/")
