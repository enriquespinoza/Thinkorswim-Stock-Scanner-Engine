from pathlib import Path

import pandas as pd

from src.data.market_data import StaticDailyBarProvider
from src.data.pipeline import download_universe_market_data


def _raw_bars() -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": 100.0,
            "Volume": 200_000.0,
        }
    )


def test_pipeline_writes_bars_and_manifest(tmp_path: Path) -> None:
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "provider_symbol": "AAPL"}]
    )
    provider = StaticDailyBarProvider({"AAPL": _raw_bars()})
    manifest = download_universe_market_data(universe, provider, tmp_path)

    assert manifest.loc[0, "symbol"] == "AAPL"
    assert bool(manifest.loc[0, "eligible"]) is True
    assert len(manifest.loc[0, "data_hash"]) == 64
    assert len(manifest.loc[0, "manifest_hash"]) == 64
    assert (tmp_path / "AAPL_1d.csv").exists()


def test_pipeline_records_provider_failure_without_aborting(tmp_path: Path) -> None:
    universe = pd.DataFrame(
        [
            {"symbol": "AAPL", "provider_symbol": "AAPL"},
            {"symbol": "MISSING", "provider_symbol": "MISSING"},
        ]
    )
    provider = StaticDailyBarProvider({"AAPL": _raw_bars()})
    manifest = download_universe_market_data(universe, provider, tmp_path)

    assert manifest["symbol"].tolist() == ["AAPL", "MISSING"]
    missing = manifest.loc[manifest["symbol"] == "MISSING"].iloc[0]
    assert missing["status"] == "error"
    assert missing["eligible"] == False
    assert "market_data_error" in missing["eligibility_reasons"]
