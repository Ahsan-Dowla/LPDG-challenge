# Architecture

## Overview

```
d:\000 LPDG\
├── main.py                  # CLI entrypoint — delegates to src.part1.pipeline
├── scripts/
│   ├── predict.py           # Canonical ranking entrypoint via src.lpdg
│   ├── evaluate.py          # Compare predictions to field-visit outcomes
│   └── backtest.py          # Walk-forward reproducibility check
├── src/
│   ├── lpdg/                # Canonical production package (all logic lives here)
│   │   ├── api/             # FastAPI application (schemas, routes, app)
│   │   ├── config/          # Constants: weeks, strategies, data paths
│   │   ├── data/            # Data loaders: telemetry, gateway master
│   │   ├── exceptions.py    # Typed exception hierarchy
│   │   └── ranking/
│   │       ├── interfaces.py    # RankingStrategy abstract base class
│   │       ├── baseline.py      # 3-sigma baseline ranker
│   │       ├── v1.py            # V1 Optimized Evidence ranker (Part 1)
│   │       ├── v2.py            # V2 Probabilistic ranker (Part 2)
│   │       └── service.py       # RankingService: orchestrates data + ranker
│   ├── services/            # Legacy compatibility shims → delegate to src.lpdg
│   │   ├── exceptions.py    # RankingServiceError = LPDGError
│   │   ├── interfaces.py    # BaseRanker = RankingStrategy
│   │   ├── v1_ranker.py     # V1OptimizedRanker(V1Ranker)
│   │   ├── v2_ranker.py     # V2ProbabilisticRanker(V2Ranker)
│   │   └── ranking_service.py  # re-exports RankingService
│   ├── part1/               # Legacy Part 1 modules (also delegate to src.lpdg)
│   │   ├── pipeline.py      # run() — called by main.py
│   │   ├── data_loader.py
│   │   ├── eligibility.py
│   │   ├── config.py
│   │   ├── ranker_baseline.py
│   │   ├── ranker_optimized.py
│   │   └── ranker_v2.py
│   └── api/                 # Legacy API app.py → uses src.services
├── tests/
│   ├── test_api.py          # API integration tests
│   ├── test_part1.py        # Part 1 ranking unit tests
│   ├── test_v2_probabilistic.py  # V2 unit tests
│   ├── test_regression_coverage.py  # Persistence bug regression
│   ├── unit/                # (expandable) unit test sub-package
│   ├── integration/         # (expandable) integration sub-package
│   └── regression/
│       └── test_frozen_outputs.py  # Hash + cell-by-cell frozen output tests
├── docs/
│   ├── architecture.md      # This file
│   ├── methodology.md       # Algorithm description
│   ├── runbook.md           # How to run / reproduce
│   └── limitations.md       # Known limitations and failure modes
├── data/                    # Raw data (gitignored)
├── outputs/                 # Generated predictions (gitignored except .gitkeep)
├── predictions.csv          # Official V1 Part 1 submission (frozen)
├── predictions_v2.csv       # V2 Part 2 challenger output (frozen)
├── validate_submission.py   # Format validator
├── Dockerfile               # Multi-stage Docker build
├── docker-compose.yml       # Local service orchestration
└── .github/workflows/ci.yml # CI pipeline
```

## Key Design Decisions

### Single Source of Truth: `src/lpdg/`
All ranking logic, data loading, and service code is canonical in `src/lpdg/`.
The `src/services/` and `src/part1/` packages are thin compatibility bridges —
they subclass or re-export from `src/lpdg/` without reimplementing logic.

### Strategy Pattern
`RankingStrategy` (abstract) is implemented by `BaselineRanker`, `V1Ranker`, and `V2Ranker`.
`RankingService` accepts any strategy via dependency injection.

### Frozen Submissions
`predictions.csv` and `predictions_v2.csv` are pinned by SHA-256 hash in CI.
They must never be silently modified.

### No Future Data Leakage
Every `get_predictions_for_week(date)` call slices telemetry with `ts_utc < cutoff`
before passing data to the ranker. The regression test suite verifies this constraint.
