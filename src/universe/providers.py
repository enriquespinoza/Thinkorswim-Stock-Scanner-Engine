from __future__ import annotations

from abc import ABC, abstractmethod
from io import StringIO

import pandas as pd
import requests

from src.universe.models import UniverseSecurity


class UniverseProvider(ABC):
    @abstractmethod
    def load(self) -> list[UniverseSecurity]:
        raise NotImplementedError


def to_yfinance_symbol(symbol: str) -> str:
    """Normalize common US equity ticker notation for Yahoo Finance."""
    return symbol.strip().upper().replace(".", "-")


class WikipediaSP500UniverseProvider(UniverseProvider):
    """Load current S&P 500 constituents from the public Wikipedia table."""

    URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def load(self) -> list[UniverseSecurity]:
        response = requests.get(
            self.URL,
            timeout=self.timeout_seconds,
            headers={"User-Agent": "Thinkorswim-Stock-Scanner-Engine/1.0"},
        )
        response.raise_for_status()
        tables = pd.read_html(StringIO(response.text))
        if not tables:
            raise ValueError("No constituent table found")

        table = tables[0]
        required = {"Symbol", "Security", "GICS Sector", "GICS Sub-Industry"}
        missing = required.difference(table.columns)
        if missing:
            raise ValueError(f"S&P 500 source is missing columns: {sorted(missing)}")

        records: list[UniverseSecurity] = []
        for row in table.to_dict(orient="records"):
            symbol = str(row["Symbol"]).strip().upper()
            records.append(
                UniverseSecurity(
                    symbol=symbol,
                    provider_symbol=to_yfinance_symbol(symbol),
                    name=str(row["Security"]).strip(),
                    sector=str(row["GICS Sector"]).strip(),
                    industry=str(row["GICS Sub-Industry"]).strip(),
                    source="wikipedia_sp500",
                )
            )
        return records


class StaticUniverseProvider(UniverseProvider):
    def __init__(self, securities: list[UniverseSecurity]) -> None:
        self.securities = list(securities)

    def load(self) -> list[UniverseSecurity]:
        return list(self.securities)
