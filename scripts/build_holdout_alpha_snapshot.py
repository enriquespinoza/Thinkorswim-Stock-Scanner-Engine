from __future__ import annotations

import argparse
from pathlib import Path

from config.alpha import ALPHA_FREEZE_DATE, ALPHA_SPEC_VERSION, HOLDOUT_POLICY
from config.data_sources import PRIMARY_RESEARCH_PROVIDER
from src.scoring.alpha import score_alpha_snapshot
from src.scoring.snapshot import build_latest_feature_snapshot
from src.validation.holdout import HoldoutNotReadyError, write_immutable_holdout_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and freeze a true-holdout Scanner Alpha V1 ranking snapshot."
    )
    parser.add_argument(
        "--provider",
        choices=("yahoo", "schwab"),
        default=PRIMARY_RESEARCH_PROVIDER,
    )
    parser.add_argument("--feature-manifest", type=Path, default=None)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("reports/validation/holdout"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    latest = build_latest_feature_snapshot(
        provider=args.provider,
        feature_manifest_path=args.feature_manifest,
    )
    scored = score_alpha_snapshot(latest)

    try:
        snapshot_path, manifest_path, digest = write_immutable_holdout_snapshot(
            scored,
            provider=args.provider,
            output_root=args.output_root,
        )
    except HoldoutNotReadyError as exc:
        latest_session = scored["timestamp"].min()
        print("=" * 88)
        print("SCANNER ALPHA V1 — HOLDOUT NOT READY")
        print("=" * 88)
        print(f"Alpha spec: {ALPHA_SPEC_VERSION}")
        print(f"Freeze date: {ALPHA_FREEZE_DATE}")
        print(f"Provider: {args.provider}")
        print(f"Latest feature session: {latest_session}")
        print(f"Status: {exc}")
        print("No holdout artifact was written.")
        return

    print("=" * 88)
    print("SCANNER ALPHA V1 — TRUE HOLDOUT SNAPSHOT")
    print("=" * 88)
    print(f"Alpha spec: {ALPHA_SPEC_VERSION}")
    print(f"Freeze date: {ALPHA_FREEZE_DATE}")
    print(f"Provider: {args.provider}")
    print(f"Rows: {len(scored)}")
    print(f"Alpha-complete rows: {int(scored['alpha_complete'].sum())}")
    print(f"Snapshot SHA-256: {digest}")
    print()
    print("Top 20 candidates:")
    print(
        scored.loc[scored["alpha_complete"]]
        .head(20)[
            [
                "alpha_rank",
                "symbol",
                "alpha_percentile",
                "momentum_252d_ex_20d",
                "ema_50_to_200",
            ]
        ]
        .to_string(index=False)
    )
    print()
    print(f"Policy: {HOLDOUT_POLICY}")
    print(f"Saved -> {snapshot_path}")
    print(f"Saved -> {manifest_path}")


if __name__ == "__main__":
    main()
