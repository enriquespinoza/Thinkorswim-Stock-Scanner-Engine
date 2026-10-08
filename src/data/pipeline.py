from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.market_data import DailyBarProvider, save_daily_bars
from src.universe.eligibility import EligibilityPolicy, evaluate_basic_eligibility
from src.utils.hashing import stable_dataframe_hash


@dataclass(frozen=True)
class DownloadResult:
    symbol: str
    rows: int
    eligible: bool
    eligibility_reasons: tuple[str, ...]
    data_hash: str
    output_path: str
    status: str
    error: str


def download_universe_market_data(
    universe: pd.DataFrame,
    provider: DailyBarProvider,
    output_dir: str | Path,
    period: str = "2y",
    interval: str = "1d",
    eligibility_policy: EligibilityPolicy = EligibilityPolicy(),
) -> pd.DataFrame:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[DownloadResult] = []
    for row in universe.to_dict(orient="records"):
        symbol = str(row["symbol"])
        provider_symbol = str(row["provider_symbol"])
        output_path = output_dir / f"{symbol.replace('/', '_')}_1d.csv"

        try:
            bars = provider.history(provider_symbol, symbol, period=period, interval=interval)
            eligible, reasons = evaluate_basic_eligibility(bars, eligibility_policy)
            data_hash = save_daily_bars(bars, output_path)
            results.append(
                DownloadResult(
                    symbol=symbol,
                    rows=len(bars),
                    eligible=eligible,
                    eligibility_reasons=reasons,
                    data_hash=data_hash,
                    output_path=str(output_path),
                    status="ok",
                    error="",
                )
            )
        except Exception as exc:
            results.append(
                DownloadResult(
                    symbol=symbol,
                    rows=0,
                    eligible=False,
                    eligibility_reasons=("market_data_error",),
                    data_hash="",
                    output_path=str(output_path),
                    status="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    manifest = pd.DataFrame(
        [
            {
                "symbol": result.symbol,
                "rows": result.rows,
                "eligible": result.eligible,
                "eligibility_reasons": "|".join(result.eligibility_reasons),
                "data_hash": result.data_hash,
                "output_path": result.output_path,
                "status": result.status,
                "error": result.error,
            }
            for result in results
        ]
    ).sort_values("symbol").reset_index(drop=True)

    digest = stable_dataframe_hash(manifest)
    manifest["manifest_hash"] = digest
    return manifest
