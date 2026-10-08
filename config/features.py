from __future__ import annotations

RETURN_WINDOWS = (1, 5, 20, 60, 126, 252)
EMA_WINDOWS = (9, 21, 50, 200)
VOLATILITY_WINDOWS = (20, 60)
RELATIVE_RETURN_WINDOWS = (20, 60)
CORRELATION_WINDOW = 60
RSI_WINDOW = 14
ATR_WINDOW = 14
LIQUIDITY_WINDOW = 20
DRAWDOWN_WINDOW = 60
ANNUALIZATION_FACTOR = 252

PORTFOLIO_REFERENCE_SYMBOLS = ("SPY", "QQQ", "TLT", "GLD", "SCHD")

SECTOR_BENCHMARKS = {
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}

REFERENCE_SYMBOLS = tuple(
    dict.fromkeys(PORTFOLIO_REFERENCE_SYMBOLS + tuple(SECTOR_BENCHMARKS.values()))
)

CORE_FEATURE_COLUMNS = (
    *(f"return_{window}d" for window in RETURN_WINDOWS),
    *(f"ema_{window}" for window in EMA_WINDOWS),
    *(f"price_to_ema_{window}" for window in EMA_WINDOWS),
    "ema_9_to_21",
    "ema_50_to_200",
    "rsi_14",
    *(f"volatility_{window}d" for window in VOLATILITY_WINDOWS),
    *(f"downside_volatility_{window}d" for window in VOLATILITY_WINDOWS),
    "current_drawdown_60d",
    "atr_14",
    "atr_pct_14",
    "median_dollar_volume_20d",
    "relative_volume_20d",
)

RELATIVE_FEATURE_COLUMNS = (
    "excess_return_spy_20d",
    "excess_return_spy_60d",
    "corr_spy_60d",
    "beta_spy_60d",
    "excess_return_sector_20d",
    "excess_return_sector_60d",
    "corr_sector_60d",
    "corr_qqq_60d",
    "corr_tlt_60d",
    "corr_gld_60d",
    "corr_schd_60d",
)

FEATURE_COLUMNS = CORE_FEATURE_COLUMNS + RELATIVE_FEATURE_COLUMNS
