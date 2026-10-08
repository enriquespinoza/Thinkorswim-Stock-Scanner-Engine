# Phase 1 — Universe and Market-Data Foundation

## Status

**COMPLETE — frozen on 2026-10-07**

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

## Point-in-time universe correction

The first live audit exposed stale constituent data. The 2026-10-07 snapshot was corrected for corporate/index actions before the phase was frozen:

- WBD removed;
- CTVA removed;
- TWLO added;
- VYLR added;
- PSKY renamed to SKYD.

The corrected universe contains 503 securities with zero duplicate symbols.

## Final ingestion audit

- universe coverage: 503 / 503 (100%);
- successful downloads: 503;
- failed downloads: 0;
- successful histories with SHA-256 hashes: 503 / 503;
- unique manifest hashes: 1;
- manifest SHA-256: `fb9b1a672cad283c1e0036a783c80c67fa7079d2b7021c4960d60086e0447d5c`;
- eligible after Phase-1 gates: 499;
- ineligible after Phase-1 gates: 4.

Short-history exclusions:

| Symbol | Rows | Reason |
| --- | ---: | --- |
| FDXF | 93 | insufficient_history |
| HONA | 80 | insufficient_history |
| Q | 238 | insufficient_history |
| VYLR | 5 | insufficient_history |

These exclusions are expected consequences of the Phase-1 minimum-history rule, not provider failures.

## Exit criteria

All Phase-1 exit criteria are satisfied:

- repository environment imports successfully;
- deterministic universe frame is built and validated;
- ticker normalization is tested;
- OHLCV normalization rejects malformed data;
- baseline eligibility checks are tested;
- market-data pipeline writes per-symbol history and an auditable manifest;
- full offline test suite passes;
- first live 503-symbol ingestion completes with zero provider failures.

Phase 2 may now begin.
