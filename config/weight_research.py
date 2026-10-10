from __future__ import annotations

RESEARCH_CONTRACT_VERSION = "phase3b-weight-research-v1"

FORWARD_RETURN_HORIZONS = (5, 20, 60)
PRIMARY_FORWARD_RETURN_HORIZON = 20

# Research snapshots are sampled weekly to reduce overlapping daily observations
# while preserving enough cross-sections for the first experimental study.
REBALANCE_FREQUENCY = "W-FRI"

# Chronological walk-forward design. A split is eligible only when the training
# window contains at least this many distinct scoring dates.
MIN_TRAINING_DATES = 52
TEST_WINDOW_DATES = 13

# Candidate group weights are searched in fixed increments and must sum to 1.
# This is a research search space, not a production scoring decision.
WEIGHT_STEP = 0.10

TOP_QUANTILE = 0.20
BOTTOM_QUANTILE = 0.20

# Penalty applied when comparing candidate models. It is deliberately modest:
# the primary objective remains out-of-sample ranking efficacy.
TURNOVER_PENALTY = 0.05

# Current Phase-2 historical files are built from the 2026-10-07 point-in-time
# universe snapshot. This is acceptable for exploratory factor research only.
SURVIVORSHIP_BIAS_WARNING = (
    "Historical Phase 3B results use the frozen 2026-10-07 universe and therefore "
    "contain survivorship bias. Do not interpret them as production-grade index "
    "backtests until point-in-time membership is implemented."
)
