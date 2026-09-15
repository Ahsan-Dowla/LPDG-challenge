# ⚡ LPDG Innovation Hub — Gateway Prioritization

> **NEXORA 2026 · LPDG Innovation Hub Selection Challenge**
>
> A deterministic, evidence-based gateway prioritization system that selects **exactly 15 gateways per week** for field visits across **8 evaluation weeks**.
---
### 🎯 At a Glance

> **Production-style gateway ranking system** for prioritizing 15 field visits per week from smart-grid telemetry.

| **Category** | **Details** |
|:---|:---|
| 📅 **Evaluation period** | `02 Feb 2026` → `23 Mar 2026` |
| 🗓️ **Evaluation horizon** | **8 weeks** · every Monday |
| 🚨 **Weekly capacity** | **15 gateways / week** |
| 📦 **Submission size** | **120 ranked decisions** |
| 🧠 **Official strategy** | **V1 — Optimized Evidence** |
| 🔬 **Challenger strategy** | **V2 — Probabilistic Expected Value** |
| ⚡ **API framework** | **FastAPI** |
| 🐳 **Containerization** | **Docker** |
| 🔄 **CI/CD** | **GitHub Actions** |
| 🧪 **Test suite** | **82 local tests** |
| 🔐 **Challenge data** | **Private · excluded from Git** |

> **Core constraint:** exactly **15 gateways must be selected every week**, producing a deterministic **120-row submission** across the 8-week evaluation period.
---
# 🚀 Quick Start

## 1. Install

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Place the supplied challenge dataset in:

```text
data/
```

> The challenge dataset is intentionally **not included in this repository**.

---

## 2. Generate the official submission

```powershell
python main.py --strategy v1
```

This generates:

```text
predictions.csv
```

The output contains exactly **120 rows**:

- 15 gateways
- × 8 evaluation weeks

---

## 3. Validate

```powershell
python validate_submission.py predictions.csv
```

Expected:

```text
predictions.csv: OK
15 ranked gateways for each of 8 weeks
```

---

## 4. Run the test suite

```powershell
python -m pytest -q
```

---

# 🧠 Solution Overview

The system transforms hourly gateway telemetry into a weekly operational decision:

```text
┌──────────────────────┐
│ Gateway Master Data  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Hourly Telemetry     │
│ • Offline duration   │
│ • Disconnections     │
│ • Reboots            │
│ • Connection signal  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Feature Engineering  │
│ • Recent severity    │
│ • Persistence        │
│ • Silence / coverage │
│ • Meter exposure     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Ranking Strategy     │
│                      │
│ V1 Official          │
│ V2 Challenger        │
│ Baseline             │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Exactly Top 15       │
│ Gateways / Week      │
└──────────┬───────────┘
           │
           ▼
      predictions.csv
```

The implementation separates **data loading**, **feature generation**, **ranking**, **evaluation**, and the **API**, allowing ranking strategies to be changed without rewriting the API layer.

---

# 🥇 Official Strategy — V1

**V1 is the frozen Part 1 answer.**

It ranks gateways using observable telemetry evidence rather than supervised labels.

### Core signals

- **Persistence** — sustained problematic hours relative to the available observation window
- **Connection interruptions** — repeated disconnection evidence
- **Offline duration** — severity of gateway unavailability
- **Silence / missing telemetry** — treated as additional operational risk
- **Meter exposure** — customer impact based on installed meters

### Persistence

The persistence calculation is coverage-aware:

```text
persistence =
    problem_hours / max(coverage_hours, 168)
```

This prevents gateways with sparse observations from appearing artificially persistent.

### Output

```text
predictions.csv
```

SHA-256:

```text
0F4D38C524EE8E224D321E6381A5CEF83BFC81EF4D0E9C2B466C8B402125F6D0
```

The frozen output is protected by regression tests and CI hash verification.

---

# 📊 V2 — Probabilistic Challenger

V2 is retained as a **Part 2 statistical/probabilistic challenger**.

It separates:

1. **Estimated gateway impairment**
2. **Operational/customer exposure**
3. **Expected value of a field visit**

Conceptually:

```text
Telemetry
    │
    ▼
Robust statistical signals
    │
    ▼
Estimated P(impaired)
    │
    ▼
Economic exposure
    │
    ▼
Expected visit value
    │
    ▼
Top 15
```

The decision score follows the form:

```text
EV =
    P(impaired) × exposure
    − (1 − P(impaired)) × visit_cost
```

V2 uses a Bayesian Beta-Binomial persistence component with a `Beta(1, 9)` prior.

### Output

```text
predictions_v2.csv
```

SHA-256:

```text
B3CD9031CA3B71BC34A02EC854D3648A0ACBF585E5FA2DE84EE55A9D152C2652
```

> **Important:** Any economic value reported for V2 is a **backtest modelling estimate**, not realized savings. It depends on assumed cost parameters.

---

# 🔬 Why V1 Is the Official Answer

V1 remains the official submission because the challenge prioritizes **transparent operational judgement and robustness** over unnecessary model complexity.

V2 is therefore kept as a challenger rather than replacing the frozen Part 1 decision.

This also keeps the system easy to explain and modify during a live evaluation.

---

# 🌐 API

Start the API with:

```powershell
venv\Scripts\python -m uvicorn src.api.app:app --reload
```

Open:

```text
http://localhost:8000/docs
```

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/predictions/{week_start}` | Top-15 gateways for a week |
| `GET` | `/gateways/{gateway_id}?week={week_start}` | Gateway score/details |
| `GET` | `/predictions/{week_start}/explain/{gateway_id}` | Explain a gateway's ranking |
| `POST` | `/predict` | Run prediction pipeline |
| `POST` | `/run` | Reload mounted data and rerun ranking |

### Live data reload

`POST /run` is designed for the live-evaluation scenario.

The service:

```text
New data placed in mounted data/
              ↓
        POST /run
              ↓
      Clear cached state
              ↓
        Reload data
              ↓
       Rerun ranking
              ↓
       Return fresh results
```

A container restart is not required.

---

# 🐳 Docker

Build and start:

```powershell
docker compose up -d --build
```

Check:

```powershell
docker compose ps
```

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
```

Stop:

```powershell
docker compose down
```

### Container design

The image uses:

- Python 3.13 slim
- Multi-stage build
- Non-root runtime user
- Docker health check
- Mounted challenge data
- Read-only data volume

The challenge dataset is **not bundled into the image**.

---

# 🔄 Reproducible Prediction Pipeline

The main CLI is intentionally simple:

```powershell
python main.py --strategy v1
```

Alternative strategies:

```powershell
python main.py --strategy v2 --out predictions_v2.csv
```

The canonical script interface is also available:

```powershell
python scripts/predict.py --strategy v1
```

Supporting utilities:

```text
scripts/
├── predict.py
├── evaluate.py
└── backtest.py
```

---

# 🧪 Testing

The project uses three test layers:

```text
tests/
├── unit/
├── integration/
└── regression/
```

### Unit tests

Validate individual pipeline and feature behaviours.

### Integration tests

Exercise:

- FastAPI endpoints
- Ranking service
- Strategy injection
- `/run`
- Explain endpoints
- Error handling
- Repeated execution

### Regression tests

Protect:

- Frozen prediction outputs
- Ranking completeness
- Output schema
- Leakage constraints
- Critical bug fixes

Run everything locally:

```powershell
python -m pytest -q
```

Current local result:

```text
82 passed
```

---

# 🔐 Public CI vs Private Challenge Data

The supplied challenge dataset is **private** and is intentionally excluded from Git.

Public GitHub Actions therefore uses:

- synthetic test fixtures for dataset-dependent integration coverage
- frozen prediction files for submission validation
- frozen-output hash checks
- dataset-independent regression tests

The CI workflow does **not** download, generate, or publish the challenge dataset.

This keeps the repository publicly accessible while preserving meaningful automated testing.

---

# ⚙️ Continuous Integration

GitHub Actions runs on pushes and pull requests.

The public CI pipeline performs:

```text
Install dependencies
        ↓
Run dataset-independent tests
        ↓
Validate predictions.csv
        ↓
Validate predictions_v2.csv
        ↓
Verify frozen V1 hash
```

The private challenge dataset is never required by the public CI workflow.

---

# 🏗️ Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── src/
│   ├── lpdg/                  # Canonical production package
│   │   ├── api/               # FastAPI application
│   │   ├── config/            # Configuration
│   │   ├── data/              # Data loaders
│   │   ├── evaluation/        # Evaluation metrics
│   │   ├── features/          # Feature engineering
│   │   ├── ranking/           # Ranking strategies
│   │   │   ├── interfaces.py
│   │   │   ├── baseline.py
│   │   │   ├── v1.py
│   │   │   ├── v2.py
│   │   │   └── service.py
│   │   └── exceptions.py
│   │
│   ├── services/              # Compatibility bridges
│   ├── part1/                 # Part 1 compatibility pipeline
│   └── api/                   # API compatibility layer
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
│
├── scripts/
│   ├── predict.py
│   ├── evaluate.py
│   └── backtest.py
│
├── docs/
│   ├── architecture.md
│   ├── methodology.md
│   ├── runbook.md
│   └── limitations.md
│
├── predictions.csv
├── predictions_v2.csv
├── predictions_baseline.csv
├── main.py
├── validate_submission.py
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── DECISIONS.md
└── AI-USAGE.md
```

---

# 📈 Evaluation & Analysis

The repository includes supporting analysis covering:

- Baseline vs optimized ranking
- Gateway exposure
- Telemetry signal relationships
- Historical field-visit outcomes
- Temporal leakage checks
- Walk-forward evaluation
- V1/V2 comparison
- Economic sensitivity
- Known false-positive and false-negative cases

See:

- [`docs/optimization-analysis.md`](docs/optimization-analysis.md)
- [`docs/optimization-audit.md`](docs/optimization-audit.md)
- [`docs/data-exploration.md`](docs/data-exploration.md)

---

# ⚠️ Known Limitations

See [`docs/limitations.md`](docs/limitations.md) for the full discussion.

Key limitations include:

### Historical labels are biased

Past field visits are not a clean supervised-learning dataset. A gateway generally needed to be selected for a visit before an engineer could confirm its condition.

### Economic assumptions

V2's expected-value score uses assumed operational cost parameters. It should therefore be interpreted as a decision model, not a measured financial result.

### Limited evaluation horizon

The official 8-week evaluation window is short for drawing strong conclusions about long-term strategy superiority.

### Telemetry ≠ customer impact

A gateway can exhibit telemetry problems while local meter buffering or backfill protects downstream meter reads.

---

# 🚫 What This System Cannot Do

The system should **not** be interpreted as:

- a guarantee that a gateway will fail
- a replacement for an engineer's diagnosis
- a causal model of gateway failures
- a perfectly calibrated probability of physical failure
- proof that every selected visit will produce a repair
- a substitute for operational judgement

The ranking is a **decision-support mechanism** designed to prioritize limited field capacity using available evidence.

---

# 📚 Documentation

| Document | Purpose |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System architecture and design |
| [`docs/methodology.md`](docs/methodology.md) | Ranking methodology |
| [`docs/runbook.md`](docs/runbook.md) | Operational runbook |
| [`docs/limitations.md`](docs/limitations.md) | Limitations and failure modes |
| [`docs/optimization-analysis.md`](docs/optimization-analysis.md) | Optimization analysis |
| [`docs/optimization-audit.md`](docs/optimization-audit.md) | Audit and robustness analysis |
| [`DECISIONS.md`](DECISIONS.md) | Engineering decision log |
| [`AI-USAGE.md`](AI-USAGE.md) | AI assistance disclosure |

---

# 🏁 Project Status

| Component | Status |
|---|:---:|
| Part 1 — Gateway Ranking | ✅ **Complete / Frozen** |
| Software Development — API | ✅ **Complete** |
| V2 Statistical Challenger | ✅ **Complete** |
| Architecture Refactor | ✅ **Complete** |
| Test Reorganization | ✅ **Complete** |
| Docker | ✅ **Complete** |
| CI/CD | ✅ **Complete** |
| Documentation | ✅ **Complete** |

---

## 👤 Submission

**Challenge:** LPDG Innovation Hub Selection Challenge 2026  
**Event:** NEXORA 2026  
**Official Part 1 strategy:** V1 — Optimized Evidence

---

> **Design principle**
>
> **Rank what the evidence supports, expose the uncertainty, and make the system easy to change when the evidence changes.**
