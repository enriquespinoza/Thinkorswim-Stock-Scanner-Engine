# Thinkorswim Stock Scanner Engine

Research-first candidate discovery for a multi-repository portfolio system.

> **Status:** Phase 1 infrastructure. This repository does not place trades and does not determine final portfolio weights.

## System boundary

```text
Thinkorswim-Stock-Scanner-Engine
        ↓ ranked candidate manifest
Thinkorswim-Portfolio-Optimization-Engine
        ↓ approved target weights
Generalized execution engine
        ↓
thinkorswim paperMoney / broker integration
```

The scanner answers **which securities deserve further evaluation**. Portfolio construction remains the responsibility of the completed `Thinkorswim-Portfolio-Optimization-Engine`. Timing and order execution remain separate.

## Phase 1 scope

Phase 1 establishes a reproducible project skeleton, interchangeable universe and market-data providers, current S&P 500 constituent ingestion, canonical ticker identities, normalized daily OHLCV data, baseline eligibility gates, deterministic hashes, and offline tests.

No alpha score, optimization, or trading logic is introduced in Phase 1.

## Baseline eligibility policy

- at least 252 daily observations;
- latest close of at least $5;
- median trailing-20-day dollar volume of at least $10 million.

The current S&P 500 list is suitable for a current scanner but must not be reused naively for historical walk-forward claims because that introduces constituent survivorship bias.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Research controls

Preserve the exact data cutoff, universe snapshot, deterministic hashes, chronological validation, versioned models/policies, and paper validation before broker execution work.

## Disclaimer

Research and educational software only. Historical or simulated results are not live trading performance.
