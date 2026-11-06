# Phase 3B — Group Weight Research

## Status

**IN VALIDATION**

Phase 3B determines how the five Phase-3 scoring groups should be weighted using
walk-forward research rather than assigning equal or subjective weights.

The five groups are:

- momentum;
- trend;
- relative strength;
- risk;
- participation.

## Research question

Which non-negative group-weight combination produces the most stable
out-of-sample cross-sectional ranking signal?

Weights must sum to 1.0.

Phase 3B does not change portfolio sizing or execution logic.

## Historical panel

The experiment reconstructs historical cross-sections from the frozen Phase-2
feature files.

For each symbol it adds forward returns at:

- 5 trading days;
- 20 trading days;
- 60 trading days.

The primary research target is the 20-day forward return.

The panel is sampled weekly using the final available market session in each
Friday-ending calendar week.

At every scoring date, the Phase-3A winsorization, z-score normalization,
signal-direction rules, and missing-data policy are reapplied cross-sectionally.

## Group signals

Within each Phase-3A feature group, the oriented standardized feature values are
averaged to produce one group-level signal:

```text
group_momentum
group_trend
group_relative_strength
group_risk
group_participation
```

This phase researches the weights **between groups**. Feature membership and
signal direction remain frozen from Phase 3A.

## Candidate weight space

Version 1 searches non-negative weights in 10-percentage-point increments.

For five groups whose weights sum to 100%, this produces 1,001 deterministic
candidate combinations.

Examples include:

```text
momentum 0.40
trend 0.20
relative_strength 0.20
risk 0.10
participation 0.10
```

and concentrated candidates such as:

```text
momentum 1.00
all other groups 0.00
```

These examples are search candidates, not recommended production weights.

## Walk-forward protocol

The study uses chronological walk-forward validation.

For each fold:

1. use at least 52 prior weekly scoring dates for training;
2. embargo training observations whose 20-day forward-return window extends
   into the test period;
3. evaluate all 1,001 candidate weight combinations on training data;
4. select the highest training objective;
5. freeze those weights;
6. evaluate them on the next 13 unseen weekly scoring dates;
7. repeat forward through history.

No future test-period data may influence the selected weights for that fold.

## Metrics

Each candidate is evaluated using:

### Rank information coefficient

Daily Spearman correlation between the research score and subsequent 20-day
return.

This is the primary ranking-efficacy measure.

### Top-minus-bottom spread

Mean forward return of the top 20% of scores minus the bottom 20%.

### Positive spread rate

Fraction of scoring dates on which the top-minus-bottom spread is positive.

### Turnover

Change in membership of the top 20% basket between scoring dates.

### Training objective

Version 1 uses:

```text
mean rank IC - 0.05 × mean top-basket turnover
```

The turnover penalty is versioned research configuration and may be challenged
in later experiments.

## Outputs

```text
reports/research/phase_3b/historical_scoring_panel.csv
reports/research/phase_3b/walk_forward_folds.csv
reports/research/phase_3b/candidate_results.csv
```

The fold output preserves:

- selected group weights;
- training metrics;
- test metrics;
- train/test date ranges.

The candidate output preserves every candidate result for every fold.

## Weight decision rule

Phase 3B should **not** choose production weights solely from the highest
aggregate backtest return.

A candidate weighting scheme should be considered robust only if:

- out-of-sample mean rank IC is positive;
- top-minus-bottom spread is positive;
- performance is not dependent on one fold;
- selected weights are reasonably stable across folds;
- turnover is operationally acceptable;
- results remain directionally similar across alternative forward horizons and
  nearby parameter settings.

The final production weight vector must be documented separately after this
research is reviewed.

## Known limitation — survivorship bias

The current historical feature set is built from the frozen 2026-10-07 universe.

Therefore historical Phase-3B results contain survivorship bias: securities that
were previously in the S&P 500 but left before the snapshot are absent, while
current constituents are represented throughout whatever history is available.

This experiment is suitable for **factor-weight research**, not for claiming a
production-grade historical S&P 500 strategy backtest.

A later data-quality phase should add point-in-time constituent membership
before performance claims are made.

## Validation commands

```bash
python -m pytest -q

python -m scripts.run_weight_research
```

## Exit criteria

Phase 3B is ready for a production-weight decision only after:

- the unit suite passes;
- historical panel construction succeeds;
- walk-forward folds are generated with the forward-label embargo;
- all 1,001 candidates are reproducibly evaluated per fold;
- out-of-sample metrics are reviewed;
- selected-weight stability is reviewed;
- survivorship bias is explicitly retained in the research record;
- no portfolio allocation or execution logic is introduced.
