from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config.data_sources import PRIMARY_RESEARCH_PROVIDER

from config.features import (
    ANNUALIZATION_FACTOR,
    ATR_WINDOW,
    CORRELATION_WINDOW,
    DRAWDOWN_WINDOW,
    EMA_WINDOWS,
    FEATURE_COLUMNS,
    LIQUIDITY_WINDOW,
    RELATIVE_RETURN_WINDOWS,
    RETURN_WINDOWS,
    RSI_WINDOW,
    SECTOR_BENCHMARKS,
    VOLATILITY_WINDOWS,
)
from config.settings import PROCESSED_DATA_DIR
from src.features.data_source import get_feature_data_source
from src.features.io import load_daily_bars


def _rsi_reference(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gains = delta.where(delta > 0.0, 0.0)
    losses = (-delta).where(delta < 0.0, 0.0)
    gains.iloc[0] = np.nan
    losses.iloc[0] = np.nan

    avg_gain = gains.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = losses.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _reference_core(bars: pd.DataFrame) -> pd.DataFrame:
    x = bars.sort_values("timestamp").reset_index(drop=True).copy()
    close = x["close"].astype(float)
    volume = x["volume"].astype(float)
    daily = close / close.shift(1) - 1.0

    for window in RETURN_WINDOWS:
        x[f"return_{window}d"] = close / close.shift(window) - 1.0

    for window in EMA_WINDOWS:
        ema = close.ewm(span=window, adjust=False, min_periods=window).mean()
        x[f"ema_{window}"] = ema
        x[f"price_to_ema_{window}"] = close / ema - 1.0

    x["ema_9_to_21"] = x["ema_9"] / x["ema_21"] - 1.0
    x["ema_50_to_200"] = x["ema_50"] / x["ema_200"] - 1.0
    x["rsi_14"] = _rsi_reference(close, RSI_WINDOW)

    for window in VOLATILITY_WINDOWS:
        x[f"volatility_{window}d"] = (
            daily.rolling(window, min_periods=window).std(ddof=1)
            * np.sqrt(ANNUALIZATION_FACTOR)
        )
        negative_only = daily.where(daily < 0.0, 0.0)
        x[f"downside_volatility_{window}d"] = (
            negative_only.pow(2)
            .rolling(window, min_periods=window)
            .mean()
            .pow(0.5)
            * np.sqrt(ANNUALIZATION_FACTOR)
        )

    rolling_peak = close.rolling(DRAWDOWN_WINDOW, min_periods=DRAWDOWN_WINDOW).max()
    x["current_drawdown_60d"] = close / rolling_peak - 1.0

    previous = close.shift(1)
    true_range = np.maximum.reduce(
        [
            (x["high"].astype(float) - x["low"].astype(float)).to_numpy(),
            (x["high"].astype(float) - previous).abs().to_numpy(),
            (x["low"].astype(float) - previous).abs().to_numpy(),
        ]
    )
    atr = pd.Series(true_range, index=x.index).rolling(
        ATR_WINDOW,
        min_periods=ATR_WINDOW,
    ).mean()
    x["atr_14"] = atr
    x["atr_pct_14"] = atr / close

    dollar_volume = close * volume
    x["median_dollar_volume_20d"] = dollar_volume.rolling(
        LIQUIDITY_WINDOW,
        min_periods=LIQUIDITY_WINDOW,
    ).median()
    x["relative_volume_20d"] = volume / volume.rolling(
        LIQUIDITY_WINDOW,
        min_periods=LIQUIDITY_WINDOW,
    ).mean()

    return x


def _attach_reference_benchmark(
    frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    label: str,
    *,
    excess: bool = False,
    beta: bool = False,
) -> pd.DataFrame:
    bench = benchmark[["timestamp", "close"]].copy()
    bench = bench.rename(columns={"close": f"benchmark_close_{label}"})

    x = frame.merge(bench, on="timestamp", how="left", validate="one_to_one")
    asset_close = x["close"].astype(float)
    benchmark_close = x[f"benchmark_close_{label}"].astype(float)
    asset_daily = asset_close / asset_close.shift(1) - 1.0
    benchmark_daily = benchmark_close / benchmark_close.shift(1) - 1.0

    if excess:
        for window in RELATIVE_RETURN_WINDOWS:
            x[f"excess_return_{label}_{window}d"] = (
                asset_close / asset_close.shift(window) - 1.0
            ) - (
                benchmark_close / benchmark_close.shift(window) - 1.0
            )

    x[f"corr_{label}_{CORRELATION_WINDOW}d"] = asset_daily.rolling(
        CORRELATION_WINDOW,
        min_periods=CORRELATION_WINDOW,
    ).corr(benchmark_daily)

    if beta:
        covariance = asset_daily.rolling(
            CORRELATION_WINDOW,
            min_periods=CORRELATION_WINDOW,
        ).cov(benchmark_daily)
        variance = benchmark_daily.rolling(
            CORRELATION_WINDOW,
            min_periods=CORRELATION_WINDOW,
        ).var(ddof=1)
        x[f"beta_{label}_{CORRELATION_WINDOW}d"] = covariance / variance.replace(0.0, np.nan)

    return x.drop(columns=[f"benchmark_close_{label}"])


def _reference_features(
    bars: pd.DataFrame,
    sector: str,
    references: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    x = _reference_core(bars)
    x = _attach_reference_benchmark(x, references["SPY"], "spy", excess=True, beta=True)
    for symbol in ("QQQ", "TLT", "GLD", "SCHD"):
        x = _attach_reference_benchmark(x, references[symbol], symbol.lower())

    sector_symbol = SECTOR_BENCHMARKS[sector]
    x = _attach_reference_benchmark(x, references[sector_symbol], "sector", excess=True)
    return x


def _same_or_close(production: float, reference: float, tolerance: float) -> tuple[bool, float]:
    if pd.isna(production) and pd.isna(reference):
        return True, 0.0
    if pd.isna(production) != pd.isna(reference):
        return False, float("inf")

    difference = abs(float(production) - float(reference))
    scale = max(1.0, abs(float(reference)))
    return difference <= tolerance * scale, difference


def audit_feature_parity(
    universe_path: Path,
    feature_manifest_path: Path,
    provider_name: str,
    tolerance: float = 1e-9,
) -> None:
    universe = pd.read_csv(universe_path).set_index("symbol")
    manifest = pd.read_csv(feature_manifest_path, keep_default_na=False)
    source = get_feature_data_source(provider_name)

    if "provider" in manifest.columns:
        manifest_providers = set(manifest["provider"].astype(str).str.lower())
        if manifest_providers != {source.name}:
            raise ValueError(
                f"Feature manifest provider mismatch: {sorted(manifest_providers)} "
                f"!= {source.name}"
            )

    reference_symbols = {"SPY", "QQQ", "TLT", "GLD", "SCHD", *SECTOR_BENCHMARKS.values()}
    references = {
        symbol: load_daily_bars(source.reference_dir / f"{symbol}_1d.csv", symbol)
        for symbol in sorted(reference_symbols)
    }

    comparisons = 0
    failures: list[dict[str, object]] = []
    max_difference = 0.0

    for row in manifest.to_dict(orient="records"):
        symbol = str(row["symbol"])
        sector = str(universe.loc[symbol, "sector"])

        raw = load_daily_bars(source.bars_dir / f"{symbol}_1d.csv", symbol)
        production = pd.read_csv(row["output_path"])
        production["timestamp"] = pd.to_datetime(production["timestamp"], utc=True)

        reference = _reference_features(raw, sector, references)

        if production.iloc[-1]["timestamp"] != reference.iloc[-1]["timestamp"]:
            failures.append(
                {
                    "symbol": symbol,
                    "feature": "timestamp",
                    "production": production.iloc[-1]["timestamp"],
                    "reference": reference.iloc[-1]["timestamp"],
                    "difference": "timestamp_mismatch",
                }
            )
            continue

        prod_latest = production.iloc[-1]
        ref_latest = reference.iloc[-1]

        for feature in FEATURE_COLUMNS:
            if feature not in production.columns:
                failures.append(
                    {
                        "symbol": symbol,
                        "feature": feature,
                        "production": "missing_column",
                        "reference": ref_latest.get(feature, np.nan),
                        "difference": "missing_column",
                    }
                )
                continue

            ok, difference = _same_or_close(
                prod_latest[feature],
                ref_latest[feature],
                tolerance,
            )
            comparisons += 1
            if np.isfinite(difference):
                max_difference = max(max_difference, difference)

            if not ok:
                failures.append(
                    {
                        "symbol": symbol,
                        "feature": feature,
                        "production": prod_latest[feature],
                        "reference": ref_latest[feature],
                        "difference": difference,
                    }
                )

    print("=" * 80)
    print("PHASE 2 FEATURE PARITY AUDIT")
    print(f"Provider: {source.name}")
    print("=" * 80)
    print(f"Symbols audited: {len(manifest)}")
    print(f"Features per symbol: {len(FEATURE_COLUMNS)}")
    print(f"Comparisons: {comparisons}")
    print(f"Tolerance: {tolerance:.1e}")
    print(f"Maximum absolute difference: {max_difference:.12e}")
    print(f"Failures: {len(failures)}")

    if failures:
        failures_frame = pd.DataFrame(failures)
        print()
        print(failures_frame.head(100).to_string(index=False))
        raise SystemExit("FEATURE PARITY AUDIT FAILED")

    print()
    print("FEATURE PARITY AUDIT PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently audit Phase-2 production feature calculations.")
    parser.add_argument("universe_csv", type=Path)
    parser.add_argument(
        "--provider",
        choices=("yahoo", "schwab"),
        default=PRIMARY_RESEARCH_PROVIDER,
    )
    parser.add_argument(
        "--feature-manifest",
        type=Path,
        default=None,
    )
    parser.add_argument("--tolerance", type=float, default=1e-9)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    source = get_feature_data_source(args.provider)
    feature_manifest = args.feature_manifest or (source.feature_dir / "feature_manifest.csv")

    audit_feature_parity(
        universe_path=args.universe_csv,
        feature_manifest_path=feature_manifest,
        provider_name=args.provider,
        tolerance=args.tolerance,
    )
