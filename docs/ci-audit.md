# Offline CI audit integration (AUDIT-003)

The workflow invokes the centralized audit runner from the top-level research repository at exact commit `0532fac27d99b408641ee7ea63a6fac8f6ad066d`. No audit report-processing logic is copied into this engine.

- PR, main-branch push, weekday schedule and manual dispatch run the existing pytest suite.
- Network access during tests is disabled through pytest-socket; no Schwab OAuth token or proprietary raw data is supplied to CI.
- Every run emits `audit-output/junit.xml`, `pytest.log`, `audit_summary.json`, and a SHA-256 summary digest.
- Broken, incomplete, empty or failed test output fails the workflow; artifacts upload even on failure.
- The evidence report **never** marks scanner signal accuracy or alpha as established; it fixes `research_acceptance=NOT_ESTABLISHED` and `broker_submission_permitted=false`.
- Daily CI is **not** a live data refresh, Schwab-vs-Yahoo independent reference adjudication, scanner walk-forward validation, or completed Phase 3B study.

GitHub's artifacts have 90-day retention here, not durable independent archival. A future audit registry must detect missed scheduled runs and preserve reviewed evidence out-of-band. The package dependencies remain partially unpinned; environment reproducibility is a separate gate.

Review PR CI and hash-linked manifest before merging. Any shared-runner upgrade requires a new explicit commit pin and review.
