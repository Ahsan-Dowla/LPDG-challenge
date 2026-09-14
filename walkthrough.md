# Developer Handoff & Walkthrough — Phase 1 & Phase 2

This document provides a concise onboarding guide for a developer taking over the repository following the completion of **Part 1 (Gateway Ranking)**, **Phase 1 (Software Development)**, and **Phase 2 (Probabilistic / ML Ranking V2)**.

---

## 1. What Exists Right Now

The repository contains a fully working, tested, and validated weekly gateway prioritization system:

1. **Frozen Part 1 Ranking Core (`src/part1/`)**:
   - Implements **Optimization V1** (`src/part1/ranker_optimized.py`), selecting the top 15 gateways based on technical severity, coverage-aware persistence, corroboration, and customer exposure.
   - Preserves the legacy **Baseline 3-Sigma** strategy via `--strategy baseline`.
   - Output `predictions.csv` satisfies all schema, ranking, score, and reason length rules (validated by `validate_submission.py`).

2. **Phase 2 Probabilistic & Expected-Value Core (`src/part1/ranker_v2.py`)**:
   - Implements **Probabilistic V2** (`--strategy v2`) formulated as a cost-sensitive decision system.
   - Computes robust MAD positive anomaly z-scores, Bayesian Beta-Binomial persistence with coverage shrinkage, and expected economic value in € (€380 wasted visit vs €600 unattended failure).
   - Validated across 22 historical weeks, delivering **92.1% Precision@15** (+7.3% over V1), cutting wasted visits by half (-24), and earning **+€23,520 (+15.8%)** in net payoff.

3. **Decoupled Application Layer (`src/services/` & `src/api/`)**:
   - `src/services/`: Contains `RankingService` and the `BaseRanker` protocol. Supports both `V1OptimizedRanker` and `V2ProbabilisticRanker`.
   - `src/api/`: FastAPI web API exposing `/health`, `/predictions/{week}`, `/gateways/{gateway_id}`, and `/predict`.
   - The API layer contains **zero** ranking logic; ranking implementations are swappable without touching API routes.

4. **Complete Test Suite (`tests/`)**:
   - 45 passing automated tests:
     - 17 Part 1 core tests (`tests/test_part1.py`)
     - 16 Web API, schema, error handling, and E2E tests (`tests/test_api.py`)
     - 1 persistence/coverage regression test (`tests/test_regression_coverage.py`)
     - 11 Phase 2 probabilistic, shrinkage, and leakage tests (`tests/test_v2_probabilistic.py`)

5. **Documentation**:
   - `README.md`: Project overview, strategies, and operational guide.
   - `DECISIONS.md`: Log of architectural and algorithmic decisions (Decisions 1–13).
   - `docs/api.md`: Comprehensive REST API documentation with curl examples.
   - `docs/optimization-analysis.md`: Ablation analysis, 22-week backtest proofs, and failure case study.
   - `AI-USAGE.md`: Transparency statement on AI tool usage.

---

## 2. Quick Handoff Commands

All commands assume you are using the project's virtual environment (`venv`).

### Run the Test Suite
```powershell
venv\Scripts\python.exe -m pytest -q
```
*Expected: `45 passed in ~50s`.*

### Generate Submission Predictions (CLI)
```powershell
# Default Optimization V1
venv\Scripts\python.exe main.py --data data --out predictions.csv

# Probabilistic V2
venv\Scripts\python.exe main.py --strategy v2 --data data --out predictions_v2.csv
```

### Validate Submission Format
```powershell
venv\Scripts\python.exe validate_submission.py predictions.csv
venv\Scripts\python.exe validate_submission.py predictions_v2.csv
```
*Expected: `predictions.csv: OK`.*

### Run Backtesting Suite
```powershell
venv\Scripts\python.exe backtest_full.py
```

### Start the REST API
```powershell
venv\Scripts\uvicorn.exe src.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive docs: `http://127.0.0.1:8000/docs`.

---

## 3. What is Intentionally Deferred

- **Docker & DevOps Infrastructure**: Containerization, Docker Compose, CI/CD GitHub Actions pipelines, container health checks, and Prometheus metrics are deferred to the DevOps phase.
