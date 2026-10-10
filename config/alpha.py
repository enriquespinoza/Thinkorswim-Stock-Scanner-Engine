from __future__ import annotations

ALPHA_SPEC_VERSION = "scanner-alpha-v1"
ALPHA_FREEZE_DATE = "2026-10-09"

PRIMARY_ALPHA_SIGNAL = "momentum_252d_ex_20d"
PRIMARY_FORWARD_HORIZON_DAYS = 20
MONITORING_FORWARD_HORIZONS_DAYS = (5, 60)

# Frozen Scanner Alpha V1 deliberately uses one signal. No optimized blend is
# permitted during holdout validation.
ALPHA_COMPONENT_WEIGHTS: dict[str, float] = {
    PRIMARY_ALPHA_SIGNAL: 1.0,
}

# Retained in holdout snapshots for diagnosis only. It does not affect alpha_score.
ALPHA_CONTEXT_FEATURES = (
    "ema_50_to_200",
)

# These categories remain outside the alpha score by design.
EXCLUDED_FROM_ALPHA = (
    "risk",
    "participation",
    "short_horizon_momentum",
    "spy_relative_returns",
    "sector_relative_returns",
)

HOLDOUT_POLICY = (
    "No feature additions, signal-direction changes, weight changes, threshold tuning, "
    "or target-horizon changes are allowed under scanner-alpha-v1. Any such change "
    "requires a new alpha specification version and a new holdout start date."
)
