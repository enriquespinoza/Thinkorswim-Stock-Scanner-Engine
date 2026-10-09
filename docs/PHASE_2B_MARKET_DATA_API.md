# Phase 2B — Market Data API Migration

## Status

**IN VALIDATION**

This phase migrates the scanner from a Yahoo-only research feed to a versioned market-data architecture with Schwab as the preferred authenticated source.

Phase 1 and Phase 2 remain frozen. Their Yahoo-derived artifacts are retained as the original research baseline and are not overwritten.

## Why this phase exists

The scanner now has enough infrastructure that data quality matters more than adding a scoring model. Before Phase 3, the project should establish a stronger market-data source and make provider changes auditable.

The migration is intentionally treated as a data-platform version change:

```text
provider raw response
        ↓
provider normalization
        ↓
canonical OHLCV contract
        ↓
Phase-2 feature engine
        ↓
feature parity / research
```

## Provider versions

### V1 baseline

```text
Yahoo Finance
→ data/raw/*.csv
→ frozen Phase-1/Phase-2 research baseline
```

### V2 candidate

```text
Schwab Trader API
→ data/providers/schwab/market-data-v1/raw/*.json
→ data/providers/schwab/market-data-v1/normalized/*.csv
→ Phase-2 feature engine
```

Raw Schwab JSON and normalized CSV are both hashed. Provider name, provider version, schema version, fetch timestamp, raw hash, normalized hash, row count, and eligibility state are stored in the Schwab manifest.

## Safety boundary

The scanner integration is market-data-only. It exposes:

- price history;
- quotes;
- market hours.

It does not expose:

- account balances;
- positions;
- order placement;
- order replacement;
- order cancellation.

Broker execution remains a separate future system boundary.

## Migration validation

Schwab does not become the scanner default simply because authentication succeeds.

The candidate provider must pass:

1. unit tests for auth/configuration and normalization;
2. full-universe Schwab ingestion;
3. raw and normalized hashing coverage;
4. cross-provider Yahoo/Schwab audit;
5. review of corporate-action and adjusted-price differences;
6. rebuild of Phase-2 features from Schwab-normalized OHLCV;
7. independent Phase-2 feature parity audit on the Schwab dataset.

## Cross-provider audit

The audit compares overlapping daily observations from Yahoo and Schwab and reports:

- overlap rows;
- latest-date agreement;
- maximum close difference in basis points;
- median close difference in basis points;
- exact volume-match rate;
- symbols requiring review.

Differences are not automatically treated as Schwab errors. Corporate actions, provider adjustment conventions, and timestamp/session handling must be investigated before deciding which series is authoritative.

## Cutover rule

Schwab becomes the default research provider only after:

- all expected symbols ingest successfully or documented exclusions are accepted;
- all successful raw and normalized artifacts have hashes;
- cross-provider discrepancies are explained;
- the Phase-2 feature engine rebuilds successfully from Schwab data;
- the independent feature parity audit passes;
- a versioned migration audit is committed.

Until then, Yahoo remains the frozen baseline and Schwab remains a candidate provider.
