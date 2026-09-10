# LPDG Innovation Hub Selection Challenge 2026 — Gateway Prioritization

A robust, evidence-based prioritization system for smart meter gateway maintenance visits, developed for the LPDG Innovation Hub Selection Challenge 2026.

The project currently implements **Part 1 (Gateway Ranking)** and **Phase 1 (Software Development)**, wrapping a frozen deterministic ranking pipeline in a clean service layer and FastAPI web application.

---

## 1. Challenge & Business Context

In modern smart metering infrastructure, communication gateways collect and transmit interval meter readings from customer premises to the utility head-end system. When gateways degrade or disconnect:
- Meter reading collection rates drop below regulatory service level agreements (SLAs).
- Billing cycles stall, requiring manual estimates or costly re-reads.
- Hardware failures can linger undetected without targeted intervention.

### Operational Constraint: 15 Visits Per Week
Field dispatch capacity is strictly limited to **15 physical on-site visits per week**. With thousands of gateways active across the network, sending technicians to healthy sites (false alarms) wastes scarce technical labor and budget. Conversely, failing to visit severely degraded gateways with large attached customer meter counts compromises network operations.

### Part 1 Objective
Produce a deterministic, weekly prioritized visit list (`predictions.csv`) for 8 scored evaluation weeks (**2026-02-02** through **2026-03-23**):
- Exactly 15 ranked gateways per week (ranks 1..15; total 120 visits).
- Evidence-based priority score and concise operational explanation (≤ 300 characters).
- Strict temporal boundary at **Monday 00:00 UTC** (zero future data leakage).
- All predictions must pass the official grader verification tool (`validate_submission.py`).

---

## 2. Ranking Strategies

The codebase supports two distinct ranking strategies under a shared execution pipeline:

### A. Baseline 3-Sigma (`--strategy baseline`)
- Computes gateway-specific mean and standard deviation over a trailing 28-day baseline for `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`.
- Flags hours in the recent 7 days where any metric exceeds $\mu + 3\sigma$.
- Ranks by total flagged-hour count.
- **Limitation**: Highly susceptible to transient spikes on otherwise healthy gateways, resulting in high false alarms (26 Normal vs 22 Schlecht, S/N = 0.85 against independent engineer review).

### B. Optimization V1 (`--strategy optimized`, Active Default)
Designed to prioritize sustained hardware/connectivity degradation while weighting business exposure:
1. **Technical Severity**: Log-transformed (`log1p`) recent 7-day cumulative offline duration ($60\%$) and disconnection count ($40\%$), normalized by active network maxima.
2. **Persistence (Coverage-Aware)**: Ratio of problem hours to expected weekly hours ($168\text{ h}$), ensuring gateways with low coverage cannot inflate persistence.
3. **Corroboration**: Log-scaled `no_conn_importance` telemetry signal ($20\%$).
4. **Business Exposure Multiplier**: Log-scaled installed customer meter count ($30\%$).
- **Performance**: Validated against independent engineer ground truth (`engineer_review_2026-02.xlsx`), capturing **92 Schlecht gateways** with only **4 Normal false alarms** (S/N = 23.00; 4.18x improvement over baseline).

---

## 3. Project Architecture

The application follows a decoupled layered architecture ensuring the API layer does not know how the ranking formulas work:

```
Client / Frontend / Tests
          │
          ▼
   FastAPI Layer (`src/api/`)
   - Routes: GET /health, GET /predictions/{week}, GET /gateways/{id}, POST /predict
   - Pydantic Schemas & Centralized Exception Handlers (no stack trace leaks)
          │
          ▼
   Service Layer (`src/services/`)
   - RankingService (caching, data management, validation)
          │
          ▼
   Ranker Abstraction (`BaseRanker` Protocol)
          │
          ▼
   V1 Adapter (`V1OptimizedRanker`)
          │
          ▼
   Frozen Part 1 Pipeline (`src/part1/`)
   - Eligibility filtering, Parquet loaders, Optimization V1 ranker
```

### Key Architectural Properties
- **Decoupled API**: Web routes call `RankingService`, which communicates via the `BaseRanker` interface.
- **Swappable Implementation**: Future Part 2 ML or statistical optimization models can be plugged in as new `BaseRanker` implementations without changing a single line of API route code.
- **Deterministic & Safe**: Preserves 100% backward compatibility with existing CLI commands and official validation scripts.

---

## 4. Repository Structure

```text
├── DECISIONS.md                  # Architectural and algorithmic decision log
├── part-1.md                     # Part 1 challenge specifications & guidelines
├── requirements.txt              # Production and test dependencies
├── main.py                       # CLI entry point for batch prediction generation
├── evaluate.py                   # Evaluation script against engineer review & read rates
├── baseline_3sigma.py            # Original reference 3-sigma implementation
├── validate_submission.py        # Official grader validation script
├── docs/
│   ├── api.md                    # Detailed REST API specification and examples
│   ├── optimization-analysis.md  # Ground-truth ablation study and strategy comparison
│   ├── optimization-audit.md     # Mathematical formulation and leakage audit
│   ├── problem-understanding.md  # Domain problem formulation
│   └── data-exploration.md       # Exploratory data analysis
├── src/
│   ├── api/                      # Web API application layer
│   │   ├── app.py                # FastAPI app factory & exception handlers
│   │   ├── routes.py             # Route definitions
│   │   └── schemas.py            # Pydantic request/response schemas
│   ├── services/                 # Domain service layer
│   │   ├── interfaces.py         # BaseRanker Protocol
│   │   ├── v1_ranker.py          # Adapter for Optimization V1 ranker
│   │   ├── ranking_service.py    # Service orchestrating data loading & ranking
│   │   └── exceptions.py         # Custom domain exceptions
│   └── part1/                    # Frozen Part 1 core pipeline
│       ├── config.py             # Scored weeks, weights, metrics configuration
│       ├── data_loader.py        # Parquet telemetry and CSV master loaders
│       ├── eligibility.py        # Temporal cutoff and commissioning filters
│       ├── ranker.py             # Baseline 3-sigma ranker
│       ├── ranker_optimized.py   # Optimization V1 ranker
│       ├── output.py             # Submission CSV exporter
│       └── pipeline.py           # Pipeline runner
└── tests/
    ├── test_part1.py             # Core Part 1 unit & pipeline tests (17 tests)
    ├── test_api.py               # API route, schema, error handling & E2E tests (16 tests)
    └── test_regression_coverage.py # Persistence partial-coverage regression test (1 test)
```

---

## 5. Quick Start & Execution

### 5.1 Environment Setup
```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 5.2 Generate Part 1 Predictions (CLI)
```powershell
# Generate predictions using default Optimization V1
python main.py --data data --out predictions.csv

# Or generate using original 3-sigma baseline
python main.py --strategy baseline --data data --out predictions_baseline.csv
```

### 5.3 Validate Submission
Run the official challenge grader validator:
```powershell
python validate_submission.py predictions.csv
```
*Expected output: `predictions.csv: OK (15 ranked gateways for each of 8 weeks)`*

### 5.4 Run Evaluation & Backtesting
Evaluate against independent engineer reviews and meter reading rates:
```powershell
python evaluate.py predictions.csv

# Or compare baseline against optimized:
python evaluate.py --compare predictions_baseline.csv predictions.csv
```

### 5.5 Start the Web API
Launch the FastAPI development server with Uvicorn:
```powershell
uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive OpenAPI documentation:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Refer to [`docs/api.md`](docs/api.md) for full endpoint specifications, payloads, and curl examples.

### 5.6 Run Automated Tests
Execute the full test suite (34 tests passing):
```powershell
python -m pytest -q
```

---

## 6. Current Project Status

- [x] **Part 1 (Gateway Ranking)**: Completed and frozen. Generates 120 validated predictions across 8 scored weeks with 4.18x improvement in target capture.
- [x] **Phase 1 (Software Development)**: Completed. Decoupled service architecture, FastAPI REST endpoints, centralized error handling, comprehensive test suite (unit, API, E2E, regression), and developer documentation.
- [ ] **Part 2 (Probabilistic/ML Optimization)**: Intentionally deferred to Phase 2.
- [ ] **Docker & DevOps Infrastructure**: Intentionally deferred to DevOps phase.
