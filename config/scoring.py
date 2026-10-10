from __future__ import annotations

SCORING_CONTRACT_VERSION = "phase3-contract-v1"

NORMALIZATION_METHOD = "winsorized_cross_sectional_zscore"
WINSOR_LOWER_QUANTILE = 0.01
WINSOR_UPPER_QUANTILE = 0.99
MIN_CROSS_SECTION_SIZE = 50

MISSING_VALUE_POLICY = "no_imputation_exclude_from_composite"
AS_OF_POLICY = "latest_common_provider_session"

# Candidate ranking signals. These establish feature membership and economic
# direction only; Phase 3A intentionally assigns no feature or group weights.
FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "momentum": (
        "return_20d",
        "return_60d",
        "return_126d",
        "return_252d",
    ),
    "trend": (
        "price_to_ema_21",
        "price_to_ema_50",
        "price_to_ema_200",
        "ema_9_to_21",
        "ema_50_to_200",
    ),
    "relative_strength": (
        "excess_return_spy_20d",
        "excess_return_spy_60d",
        "excess_return_sector_20d",
        "excess_return_sector_60d",
    ),
    "risk": (
        "volatility_20d",
        "volatility_60d",
        "downside_volatility_20d",
        "downside_volatility_60d",
        "current_drawdown_60d",
        "atr_pct_14",
    ),
    "participation": (
        "relative_volume_20d",
    ),
}

# +1 means a larger raw value maps to a larger standardized signal.
# -1 means a smaller raw value maps to a larger standardized signal.
SIGNAL_DIRECTIONS: dict[str, int] = {
    "return_20d": 1,
    "return_60d": 1,
    "return_126d": 1,
    "return_252d": 1,
    "price_to_ema_21": 1,
    "price_to_ema_50": 1,
    "price_to_ema_200": 1,
    "ema_9_to_21": 1,
    "ema_50_to_200": 1,
    "excess_return_spy_20d": 1,
    "excess_return_spy_60d": 1,
    "excess_return_sector_20d": 1,
    "excess_return_sector_60d": 1,
    "volatility_20d": -1,
    "volatility_60d": -1,
    "downside_volatility_20d": -1,
    "downside_volatility_60d": -1,
    # Drawdown is <= 0; values closer to zero are preferred.
    "current_drawdown_60d": 1,
    "atr_pct_14": -1,
    "relative_volume_20d": 1,
}

# Retained in the snapshot for research/diagnostics but deliberately excluded
# from Phase 3A candidate ranking signals.
CONTEXT_FEATURES = (
    "return_1d",
    "return_5d",
    "ema_9",
    "ema_21",
    "ema_50",
    "ema_200",
    "price_to_ema_9",
    "rsi_14",
    "atr_14",
    "median_dollar_volume_20d",
    "corr_spy_60d",
    "beta_spy_60d",
    "corr_sector_60d",
    "corr_qqq_60d",
    "corr_tlt_60d",
    "corr_gld_60d",
    "corr_schd_60d",
)

SCORING_FEATURES = tuple(
    feature
    for features in FEATURE_GROUPS.values()
    for feature in features
)
