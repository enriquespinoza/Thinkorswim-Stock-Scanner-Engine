from __future__ import annotations

import argparse
from pathlib import Path

from config.data_sources import PRIMARY_RESEARCH_PROVIDER
from config.scoring import SCORING_CONTRACT_VERSION
from src.scoring.normalization import normalize_scoring_snapshot
from src.scoring.snapshot import build_latest_feature_snapshot
from src.utils.hashing import stable_dataframe_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase 3A scoring-ready cross-sectional snapshot."
    )
    parser.add_argument(
        "--provider",
        choices=("yahoo", "schwab"),
        default=PRIMARY_RESEARCH_PROVIDER,
    )
    parser.add_argument("--feature-manifest", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/scoring/scoring_snapshot.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    snapshot = build_latest_feature_snapshot(
        provider=args.provider,
        feature_manifest_path=args.feature_manifest,
    )
    normalized = normalize_scoring_snapshot(snapshot)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(args.output, index=False)

    digest = stable_dataframe_hash(normalized)

    print(f"Scoring contract: {SCORING_CONTRACT_VERSION}")
    print(f"Provider: {args.provider}")
    print(f"Symbols: {len(normalized)}")
    print(f"Scoring-complete symbols: {int(normalized['scoring_complete'].sum())}")
    print(f"Symbols with missing scoring inputs: {int((~normalized['scoring_complete']).sum())}")
    print(f"Snapshot SHA-256: {digest}")
    print(f"Saved -> {args.output}")
    print("Composite score: NOT IMPLEMENTED")
    print("Ranking: NOT IMPLEMENTED")


if __name__ == "__main__":
    main()
