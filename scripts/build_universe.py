from __future__ import annotations

from datetime import datetime, timezone

from config.settings import UNIVERSE_DIR
from src.universe.builder import build_universe_frame, save_universe_snapshot
from src.universe.providers import WikipediaSP500UniverseProvider


def main() -> None:
    as_of = datetime.now(timezone.utc).date().isoformat()
    provider = WikipediaSP500UniverseProvider()
    universe = build_universe_frame(provider)
    output = UNIVERSE_DIR / f"sp500_{as_of}.csv"
    digest = save_universe_snapshot(universe, output)

    print(f"Saved {len(universe)} securities -> {output}")
    print(f"Universe SHA-256: {digest}")


if __name__ == "__main__":
    main()
