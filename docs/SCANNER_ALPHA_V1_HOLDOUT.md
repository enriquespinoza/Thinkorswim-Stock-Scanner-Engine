# Scanner Alpha V1 — Freeze and Holdout Protocol

## Frozen specification

- Version: `scanner-alpha-v1`
- Freeze date: 2026-10-09
- Primary horizon: 20 trading days
- Monitoring horizons: 5 and 60 trading days
- Alpha signal: `momentum_252d_ex_20d`
- Alpha weight: 100%
- Context-only feature: `ema_50_to_200`

The alpha signal is the 252-trading-day return excluding the most recent
20 trading days:

```text
momentum_252d_ex_20d = (1 + return_252d) / (1 + return_20d) - 1
```

Cross-sectional ranking uses the existing winsorized z-score policy.

## Explicit exclusions

The following do not affect Scanner Alpha V1:

- volatility, downside volatility, drawdown, ATR, beta, or correlations;
- relative volume;
- 20-day and 60-day raw momentum;
- SPY-relative or sector-relative returns;
- portfolio sizing or execution logic.

Risk belongs to the Portfolio Optimization Engine. Execution belongs to the
Execution Engine.

## True-holdout rules

A valid holdout snapshot must:

1. use a market session strictly after 2026-10-09;
2. use one common market session across the cross-section;
3. use the frozen production data path and alpha specification;
4. be written once and never overwritten;
5. record a deterministic snapshot hash before outcomes are known.

No feature additions, signal-direction changes, weight changes, threshold
changes, or target-horizon changes are permitted under `scanner-alpha-v1`.
Any such change creates a new version and restarts the holdout clock.

## Validation metrics

Primary statistical metric:

- cross-sectional 20-day Rank IC.

Economic confirmation metrics:

- top-minus-bottom 20-day forward-return spread;
- positive IC rate;
- positive spread rate;
- top-basket turnover.

Secondary diagnostics:

- 5-day and 60-day Rank IC and spreads.

## paperMoney protocol

The scanner itself does not place orders. Each eligible validation session
produces an immutable ranked candidate file. The downstream paperMoney test
must consume that file without changing alpha ranks.

For each paperMoney observation record:

- scanner snapshot date and SHA-256;
- alpha specification version;
- selected symbols and ranks;
- portfolio optimizer output, if used;
- intended order time and actual fill;
- quantity, fill price, and transaction assumptions;
- exits and realized P&L;
- 5-, 20-, and 60-trading-day mark-to-market outcomes.

PaperMoney execution results must be stored separately from alpha research so
execution quality cannot be confused with ranking quality.

## Promotion rule

Scanner Alpha V1 remains a validation model until sufficient forward evidence
exists. Historical research results are not a substitute for the true holdout.
A production promotion decision should consider Rank IC stability, economic
spread, turnover, paperMoney implementation quality, and observed failure
modes together.

No live trading is authorized by this repository.
