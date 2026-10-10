# Phase 3 — Scoring and Ranking

## Status

**PHASE 3A — SCORING CONTRACT / NORMALIZATION**

Phase 3 consumes the frozen Schwab V2 Phase-2 feature layer and will eventually
produce a ranked candidate universe.

Phase 3 does **not** perform portfolio allocation or order execution. Those remain
separate downstream systems.

## Phase 3A objective

Before assigning any score weights, freeze the mechanics that turn the latest
cross-section of Phase-2 features into comparable ranking signals.

Phase 3A defines:

- candidate scoring features;
- feature groups;
- signal direction;
- cross-sectional normalization;
- winsorization;
- missing-value handling;
- scoring-ready snapshot schema;
- deterministic validation tests.

It intentionally does **not** define:

- feature weights;
- group weights;
- composite scores;
- ranks;
- portfolio weights;
- entry/exit signals;
- orders.

## Input contract

Default research provider:

```text
Schwab V2 / market-data-v1
```

Input source:

```text
data/processed/providers/schwab/market-data-v1/features/feature_manifest.csv
```

The scorer reads the latest row from every feature file represented by the
feature manifest.

## Feature groups

### Momentum

- return_20d
- return_60d
- return_126d
- return_252d

Higher is preferred.

### Trend

- price_to_ema_21
- price_to_ema_50
- price_to_ema_200
- ema_9_to_21
- ema_50_to_200

Higher is preferred.

Raw EMA price levels are deliberately excluded because they are not comparable
across securities.

### Relative strength

- excess_return_spy_20d
- excess_return_spy_60d
- excess_return_sector_20d
- excess_return_sector_60d

Higher is preferred.

### Risk

- volatility_20d
- volatility_60d
- downside_volatility_20d
- downside_volatility_60d
- current_drawdown_60d
- atr_pct_14

Lower volatility/downside volatility/ATR percentage is preferred.

Current drawdown is non-positive, so a value closer to zero is preferred.

### Participation

- relative_volume_20d

Higher is preferred.

Absolute median dollar volume is retained as context because liquidity is
already enforced by the upstream eligibility gate. It is not a Phase-3A
ranking factor.

## Context-only features

The following remain available for research and later model experiments but do
not enter the Phase-3A candidate signal set:

- return_1d
- return_5d
- ema_9
- ema_21
- ema_50
- ema_200
- price_to_ema_9
- rsi_14
- atr_14
- median_dollar_volume_20d
- corr_spy_60d
- beta_spy_60d
- corr_sector_60d
- corr_qqq_60d
- corr_tlt_60d
- corr_gld_60d
- corr_schd_60d

Correlations and beta are retained for later diversification/portfolio logic
rather than mixed into the initial security-selection score.

## Normalization

Method:

```text
winsorized cross-sectional z-score
```

For each scoring feature on each scoring date:

1. use only the current cross-section;
2. preserve missing values;
3. winsorize valid observations at the 1st and 99th percentiles;
4. calculate population z-scores on the winsorized cross-section;
5. multiply by the feature's signal direction so larger standardized values
   always mean a more favorable candidate signal.

This prevents raw units such as returns, volatility, and ATR percentage from
dominating merely because of scale.

## Missing values

Policy:

```text
no imputation
```

A missing raw scoring feature remains missing after normalization.

Each row receives:

- `missing_<feature>`;
- `scoring_missing_count`;
- `scoring_complete`.

A future composite-score version must explicitly decide how incomplete rows are
handled. Phase 3A does not silently substitute zero, means, medians, or sector
values.

## Output

Default path:

```text
data/processed/scoring/scoring_snapshot.csv
```

The file includes:

- raw Phase-2 features;
- oriented standardized `z_<feature>` columns;
- per-feature missing flags;
- total missing count;
- scoring-complete flag.

It does not contain `score`, `composite_score`, `rank`, or
`scanner_rank`.

## Validation

Run:

```bash
python -m pytest -q

python -m scripts.build_scoring_snapshot
```

The snapshot builder must report:

- provider;
- symbol count;
- scoring-complete count;
- incomplete count;
- deterministic snapshot SHA-256;
- confirmation that composite scoring/ranking is not implemented.

## Exit criteria for Phase 3A

Phase 3A is ready to freeze when:

- all unit tests pass;
- the Schwab scoring snapshot builds across the eligible universe;
- all expected scoring features receive oriented standardized signals;
- missing values remain missing;
- no score/rank columns exist;
- the snapshot hash is recorded;
- scoring/group weights are reviewed and versioned separately in Phase 3B.
