from __future__ import annotations

import argparse
from pathlib import Path

from config.weight_research import (
    RESEARCH_CONTRACT_VERSION,
    SURVIVORSHIP_BIAS_WARNING,
)
from src.scoring.historical import build_historical_scoring_panel
from src.scoring.weight_research import walk_forward_weight_research
from src.utils.hashing import stable_dataframe_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 3B walk-forward group-weight research."
    )
    parser.add_argument(
        "--provider",
        choices=("yahoo", "schwab", "schwab-research"),
        default="schwab-research",
    )
    parser.add_argument("--feature-manifest", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/research/phase_3b"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    panel = build_historical_scoring_panel(
        provider=args.provider,
        feature_manifest_path=args.feature_manifest,
    )
    folds, candidates = walk_forward_weight_research(panel)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    panel_path = args.output_dir / "historical_scoring_panel.csv"
    folds_path = args.output_dir / "walk_forward_folds.csv"
    candidates_path = args.output_dir / "candidate_results.csv"

    panel.to_csv(panel_path, index=False)
    folds.to_csv(folds_path, index=False)
    candidates.to_csv(candidates_path, index=False)

    print("=" * 88)
    print("PHASE 3B WALK-FORWARD WEIGHT RESEARCH")
    print("=" * 88)
    print(f"Contract: {RESEARCH_CONTRACT_VERSION}")
    print(f"Provider: {args.provider}")
    print(f"Historical panel rows: {len(panel)}")
    print(f"Historical scoring dates: {panel['session_date'].nunique()}")
    print(f"Walk-forward folds: {len(folds)}")
    print(f"Panel SHA-256: {stable_dataframe_hash(panel)}")
    print()
    print("Mean out-of-sample metrics:")
    print(f"  rank IC: {folds['test_mean_rank_ic'].mean():.6f}")
    print(
        "  top-bottom spread: "
        f"{folds['test_mean_top_bottom_spread'].mean():.6f}"
    )
    print(
        "  positive spread rate: "
        f"{folds['test_positive_spread_rate'].mean():.2%}"
    )
    print(f"  turnover: {folds['test_mean_turnover'].mean():.2%}")
    print()
    print("Mean selected group weights:")
    for column in sorted(c for c in folds.columns if c.startswith("weight_")):
        print(f"  {column.removeprefix('weight_')}: {folds[column].mean():.3f}")
    print()
    print(f"WARNING: {SURVIVORSHIP_BIAS_WARNING}")
    print()
    print(f"Saved -> {panel_path}")
    print(f"Saved -> {folds_path}")
    print(f"Saved -> {candidates_path}")


if __name__ == "__main__":
    main()
