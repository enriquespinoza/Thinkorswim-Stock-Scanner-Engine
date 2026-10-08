from __future__ import annotations

from config.features import REFERENCE_SYMBOLS
from config.settings import DEFAULT_INTERVAL, DEFAULT_LOOKBACK_PERIOD, RAW_DATA_DIR
from src.data.market_data import YFinanceDailyBarProvider, save_daily_bars


def main() -> None:
    provider = YFinanceDailyBarProvider()
    output_dir = RAW_DATA_DIR / "references"
    output_dir.mkdir(parents=True, exist_ok=True)

    for symbol in REFERENCE_SYMBOLS:
        bars = provider.history(
            provider_symbol=symbol,
            canonical_symbol=symbol,
            period=DEFAULT_LOOKBACK_PERIOD,
            interval=DEFAULT_INTERVAL,
        )
        output = output_dir / f"{symbol}_1d.csv"
        digest = save_daily_bars(bars, output)
        print(f"{symbol}: {len(bars)} rows -> {output} [{digest}]")


if __name__ == "__main__":
    main()
