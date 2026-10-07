# Phase 1 — Universe and Market-Data Foundation

## Objective

Create a deterministic, provider-independent foundation for future stock-scanner research.

## Decisions

- Start with the S&P 500 as the initial equity universe.
- Save the constituent universe as a dated snapshot before downloading prices.
- Preserve canonical symbols separately from vendor-specific symbols.
- Normalize all daily bars to one schema.
- Keep providers behind interfaces so Yahoo Finance can later be replaced or supplemented by Schwab without changing downstream feature code.
- Make tests fully offline using static providers.
- Hash all saved research inputs.
- Do not introduce alpha/scoring logic during Phase 1.

## Exit criteria

Phase 1 is complete when:

- the repository environment imports successfully;
- a deterministic universe frame can be built and validated;
- ticker normalization is tested;
- OHLCV normalization rejects malformed data;
- baseline eligibility checks are tested;
- a market-data pipeline can write per-symbol history and an auditable manifest;
- the full test suite passes locally.
