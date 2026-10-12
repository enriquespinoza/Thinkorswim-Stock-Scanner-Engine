from __future__ import annotations

import argparse
from pathlib import Path

from config.scanner_handoff import DEFAULT_CANDIDATE_LIMIT
from src.handoff.optimizer import write_candidate_handoff


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export an immutable Scanner Alpha V1 candidate handoff for the Portfolio Optimization Engine."
    )
    parser.add_argument(
        "--alpha-ranking",
        type=Path,
        required=True,
        help="Immutable scanner alpha_ranking.csv.",
    )
    parser.add_argument(
        "--alpha-manifest",
        type=Path,
        required=True,
        help="Companion immutable scanner manifest.json.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=DEFAULT_CANDIDATE_LIMIT,
        help="Number of contiguous top-ranked candidates to export.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults beside the holdout artifacts under optimizer_handoff/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.output_dir is None:
        args.output_dir = args.alpha_ranking.parent / "optimizer_handoff"

    candidate_csv, candidate_manifest, manifest = write_candidate_handoff(
        alpha_ranking_path=args.alpha_ranking,
        alpha_manifest_path=args.alpha_manifest,
        output_dir=args.output_dir,
        candidate_limit=args.candidate_limit,
    )

    print("=" * 88)
    print("SCANNER -> PORTFOLIO OPTIMIZER HANDOFF")
    print("=" * 88)
    print(f"Contract: {manifest['handoff_contract_version']}")
    print(f"Alpha spec: {manifest['scanner_alpha_spec_version']}")
    print(f"Provider: {manifest['scanner_provider']}")
    print(f"As-of session: {manifest['as_of_session']}")
    print(f"Candidates: {manifest['candidate_count']}")
    print(f"Candidate limit: {manifest['candidate_limit']}")
    print(f"Selection policy: {manifest['selection_policy']}")
    print(f"Scanner snapshot SHA-256: {manifest['scanner_snapshot_sha256']}")
    print(f"Candidate CSV SHA-256: {manifest['candidate_csv_sha256']}")
    print()
    print(f"Saved -> {candidate_csv}")
    print(f"Saved -> {candidate_manifest}")


if __name__ == "__main__":
    main()
