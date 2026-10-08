from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class UniverseSecurity:
    symbol: str
    provider_symbol: str
    name: str
    sector: str | None = None
    industry: str | None = None
    source: str = "unknown"

    def as_record(self) -> dict[str, str | None]:
        return asdict(self)
