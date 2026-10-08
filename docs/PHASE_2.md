# Phase 2 — Feature Engineering

## Status

**IN VALIDATION**

Phase 2 is not frozen until the production feature build and independent all-symbol parity audit both pass on the Phase-1 frozen universe/data snapshot.

## Objective

Transform normalized daily OHLCV data into deterministic, point-in-time-safe research features without introducing a scanner score, ranking rule, or portfolio allocation decision.

## Feature contract

### Multi-horizon returns

- 1-day
- 5-day
- 20-day
- 60-day
- 126-day
- 252-day

### Trend

- EMA 9
- EMA 21
- EMA 50
- EMA 200
- price-to-EMA distance for each EMA
- EMA 9 / EMA 21 spread
- EMA 50 / EMA 200 spread

### Momentum

- Wilder RSI 14

Multi-horizon returns are retained as the primary direct momentum measures rather than creating redundant duplicate momentum columns.

### Risk

- annualized realized volatility: 20d, 60d
- annualized downside volatility: 20d, 60d
- current 60-day drawdown
- ATR 14
- ATR 14 as a percentage of close

### Liquidity / participation

- median 20-day dollar volume
- relative volume versus trailing 20-day mean

### Market-relative features

Versus SPY:

- 20-day excess return
- 60-day excess return
- 60-day correlation
- 60-day beta

### Sector-relative features

Each GICS sector maps to one SPDR sector ETF:

| GICS sector | Benchmark |
| --- | --- |
| Communication Services | XLC |
| Consumer Discretionary | XLY |
| Consumer Staples | XLP |
| Energy | XLE |
| Financials | XLF |
| Health Care | XLV |
| Industrials | XLI |
| Information Technology | XLK |
| Materials | XLB |
| Real Estate | XLRE |
| Utilities | XLU |

Features:

- 20-day sector excess return
- 60-day sector excess return
- 60-day sector correlation

### Portfolio-reference correlations

60-day correlations are calculated against:

- SPY
- QQQ
- TLT
- GLD
- SCHD

These are reference features only. They do not determine portfolio weights.

## Point-in-time rules

Phase-2 features must obey:

- no forward returns in production feature files;
- no future price observations in rolling calculations;
- no forward filling benchmark prices across missing sessions;
- exact timestamp alignment for benchmark-relative calculations;
- feature values may be NaN until their required lookback exists;
- only Phase-1-eligible securities enter the production feature build.

## Production outputs

Per-symbol files:

```text
data/processed/features/<SYMBOL>_features.csv
```

Feature manifest:

```text
data/processed/features/feature_manifest.csv
```

The manifest contains symbol, sector, sector benchmark, row count, feature hash, output path, and a shared deterministic manifest hash.

## Validation gates

### Gate 1 — unit tests

Tests cover:

- return formula parity;
- EMA algebra;
- RSI bounds;
- volatility sign constraints;
- drawdown sign constraints;
- ATR positivity;
- benchmark-return/correlation/beta behavior;
- missing benchmark-session behavior;
- full feature-column contract;
- latest-row completeness with sufficient synthetic history.

### Gate 2 — independent feature parity audit

`scripts/audit_feature_parity.py` independently recomputes the latest feature vector for every generated symbol without calling the production feature functions.

The audit fails on:

- missing feature columns;
- timestamp mismatch;
- NaN mismatch;
- numerical mismatch beyond tolerance.

Default tolerance:

```text
1e-9 relative scale
```

No scanner score should be implemented until this audit passes.

## Local validation sequence

```bash
git checkout phase-2-feature-engineering
git pull origin phase-2-feature-engineering

python -m pytest -q

python -m scripts.download_reference_data

python -m scripts.build_features \
  data/universe/sp500_2026-10-07.csv \
  data/raw/download_manifest.csv

python -m scripts.audit_feature_parity \
  data/universe/sp500_2026-10-07.csv
```

## Exit criteria

Phase 2 may be frozen when:

- the full unit suite passes;
- all 499 Phase-1-eligible symbols produce feature files;
- all generated feature files receive deterministic hashes;
- the feature manifest has one deterministic manifest hash;
- the independent all-symbol parity audit passes;
- no scoring/ranking model has been introduced prematurely.
