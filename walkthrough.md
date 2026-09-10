# Developer Handoff & Walkthrough — Phase 1

This document provides a concise onboarding guide for a developer taking over the repository following the completion of **Part 1 (Gateway Ranking)** and **Phase 1 (Software Development)**.

---

## 1. What Exists Right Now

The repository contains a fully working, tested, and validated weekly gateway prioritization system:

1. **Frozen Part 1 Ranking Core (`src/part1/`)**:
   - Implements **Optimization V1**, selecting the top 15 gateways for each of the 8 scored weeks based on technical severity, coverage-aware persistence, corroboration, and customer exposure.
   - Preserves the legacy **Baseline 3-Sigma** strategy via `--strategy baseline`.
   - Output `predictions.csv` satisfies all schema, ranking, score, and reason length rules (validated by `validate_submission.py`).

2. **Decoupled Application Layer (`src/services/` & `src/api/`)**:
   - `src/services/`: Contains `RankingService` and the `BaseRanker` protocol. The current algorithm is wrapped in `V1OptimizedRanker`.
   - `src/api/`: FastAPI web API exposing `/health`, `/predictions/{week}`, `/gateways/{gateway_id}`, and `/predict`.
   - The API layer contains **zero** ranking logic; ranking implementations can be swapped without touching API routes.

3. **Complete Test Suite (`tests/`)**:
   - 34 passing automated tests:
     - 17 Part 1 core tests (`tests/test_part1.py`)
     - 16 Web API, schema, error handling, and E2E tests (`tests/test_api.py`)
     - 1 persistence/coverage regression test (`tests/test_regression_coverage.py`)

4. **Documentation**:
   - `README.md`: Project overview and operational guide.
   - `DECISIONS.md`: Log of architectural and algorithmic decisions (Decisions 1–12).
   - `docs/api.md`: Comprehensive REST API documentation with curl examples.
   - `docs/optimization-analysis.md` & `docs/optimization-audit.md`: Ablation analysis and mathematical proofs.
   - `AI-USAGE.md`: Transparency statement on AI tool usage.

---

## 2. Quick Handoff Commands

All commands assume you are using the project's virtual environment (`venv`).

### Run the Test Suite
```powershell
venv\Scripts\python.exe -m pytest -q
```
*Expected: `34 passed in ~15s`.*

### Generate Submission Predictions (CLI)
```powershell
venv\Scripts\python.exe main.py --data data --out predictions.csv
```
*Expected: `[optimized] wrote predictions.csv — 120 rows over 8 weeks`.*

### Validate Submission Format
```powershell
venv\Scripts\python.exe validate_submission.py predictions.csv
```
*Expected: `predictions.csv: OK`.*

### Start the REST API
```powershell
venv\Scripts\uvicorn.exe src.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive docs: `http://127.0.0.1:8000/docs`.

### Test Endpoints Quickly via Curl / PowerShell
```powershell
# Health check
curl http://127.0.0.1:8000/health

# Scored week predictions
curl http://127.0.0.1:8000/predictions/2026-03-23

# Gateway explanation
curl http://127.0.0.1:8000/gateways/02423E0E6E9F?week=2026-02-02

# Trigger rerun
curl -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" -d '{"week_start": "2026-03-23"}'
```

---

## 3. What is Intentionally Deferred

To maintain strict phase boundaries:
- **Part 2 (Probabilistic/ML Optimization)**: No advanced machine learning, predictive failure models, or feature engineering beyond Optimization V1 has been implemented yet.
- **Docker & DevOps**: Containerization, CI/CD pipelines, Prometheus monitoring, and container health checks are deferred to the DevOps phase.
