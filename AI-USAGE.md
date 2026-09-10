# AI Usage Transparency Statement

This document details how AI assistance (specifically Google Antigravity / Gemini models) was utilized throughout the development of **Part 1 (Gateway Ranking)** and **Phase 1 (Software Development)** for the LPDG Innovation Hub Selection Challenge 2026.

---

## 1. Principles of AI Use

1. **Transparency & Honesty**: All code, documentation, and tests developed with AI assistance are explicitly acknowledged.
2. **Deterministic Verification**: No AI-generated output was accepted without local automated testing (`pytest`, `validate_submission.py`, manual CLI checks).
3. **No Ground-Truth Leakage**: AI was not used to synthesize fake data, bypass cutoffs, or invent ungrounded explanations.

---

## 2. Areas of AI Assistance

### 2.1 Exploration & Reasoning Assistance
- **Data Understanding**: Used to summarize large Parquet schema definitions and inspect relationships across datasets (`telemetry`, `gateway_master`, `engineer_review`, `field_visits`, `meter_read_success`).
- **Hypothesis Formulation**: Assisted in reasoning about the limitations of 3-sigma anomaly counting (identifying sensitivity to single-hour outliers and lack of persistence modeling).
- **Ablation Structuring**: Assisted in structuring the mathematical formulation for Optimization V1 (bounded sub-scores, log-normalization, persistence scaling).

### 2.2 Implementation Assistance
- **Part 1 Core Pipeline**:
  - Implementation of ID canonicalization (`normalize_gateway_id`).
  - Active gateway temporal cutoff filtering (`active_gateways`).
  - Implementation of the Optimization V1 ranking algorithm (`rank_week_optimized`, `build_predictions_optimized`).
- **Phase 1 Software Development (API & Service Layer)**:
  - Scaffolding of the decoupled architecture: `RankingService`, `BaseRanker` protocol, and `V1OptimizedRanker` adapter.
  - Creation of FastAPI routes (`/health`, `/predictions/{week}`, `/gateways/{gateway_id}`, `/predict`) and Pydantic validation schemas.
  - Implementation of centralized exception handlers ensuring clean JSON responses without stack trace leaks.

### 2.3 Testing Assistance
- **Test Generation**:
  - Authored parameterized unit and integration tests in `tests/test_part1.py` and `tests/test_api.py`.
  - Authored the end-to-end integration test exercising the full request flow (API -> service -> real telemetry -> V1 ranker).
  - Authored the dedicated regression test in `tests/test_regression_coverage.py` protecting against treating partial-coverage gateways as 100% persistent.
- **Verification**: Executed the test suite locally via `pytest` to confirm 100% pass rates (34/34 passing).

### 2.4 Documentation Assistance
- Drafted `README.md`, `docs/api.md`, `docs/optimization-audit.md`, and `walkthrough.md`.
- Maintained `DECISIONS.md` entries (Decisions 1 through 12).

---

## 3. Human Verification & Oversight

All AI-suggested code and documentation underwent strict human verification:
- **Algorithm Invariance**: Ensured Part 1 ranking logic remained completely frozen and deterministic during API construction.
- **Grader Validation**: Independently ran `validate_submission.py predictions.csv` to ensure grader compliance.
- **Git Hygiene**: Ensured raw challenge data, temporary Parquet outputs, and scratch files were strictly excluded from commits.
