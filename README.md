# LPDG Innovation Hub Selection Challenge 2026 — Gateway Prioritization

A deterministic, evidence-based gateway visit prioritization system for the
LPDG Innovation Hub Selection Challenge 2026, delivering exactly 15 ranked
field visit recommendations per week across 8 scored evaluation weeks.

---

## Quick Start

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Generate official Part 1 predictions (V1 — frozen)
python main.py

# Generate Part 2 probabilistic predictions (V2 — challenger)
python main.py --strategy v2 --out predictions_v2.csv

# Validate format
python validate_submission.py predictions.csv

# Run all tests
python -m pytest -q
```

---

## Challenge Summary

| Item | Value |
|------|-------|
| Evaluation period | 2026-02-02 → 2026-03-23 (8 Mondays) |
| Visits per week | 15 (exactly) |
| Total submission rows | 120 |
| Official strategy | V1 Optimized Evidence (`--strategy optimized`) |
| Challenger strategy | V2 Probabilistic (`--strategy v2`) |
| Tests passing | 45 |

---

## Strategies

### V1 — Optimized Evidence Ranker (official Part 1 answer)

Scores each gateway using:
- **Persistence**: `problem_hours / max(coverage_hours, 168)` — guards against
  inflating gateways with sparse telemetry
- **Silence penalty**: hours with no telemetry treated as at-risk
- **Metric bonus**: connection interruptions weighted above raw offline duration
- **Meter exposure**: log-scaled customer count

Output: `predictions.csv` (SHA-256: `0F4D38C5...6D0`)

### V2 — Probabilistic Expected-Value Ranker (Part 2 challenger)

Separates **impairment probability** from **economic exposure** and combines
them into an estimated visit value in euros:

```
EV = P(impaired) × exposure - (1 − P(impaired)) × visit_cost
```

P(impaired) is estimated via a Bayesian persistence model with Beta prior.
Score is the expected economic value of dispatching a technician to that site.

Output: `predictions_v2.csv` (SHA-256: `B3CD9031...52`)

> **Note**: The ~€172,520 simulated economic value is a modelling estimate,
> not a realized saving. V1 and V2 had identical engineer-confirmed visit
> totals (89 each) across the 8 evaluation weeks.

---

## Repository Layout

```
.
├── main.py                    # CLI entrypoint (delegates to src.part1.pipeline)
├── scripts/
│   ├── predict.py             # Canonical ranking CLI via src.lpdg
│   ├── evaluate.py            # Evaluate against field-visit outcomes
│   └── backtest.py            # Walk-forward reproducibility check
├── src/
│   ├── lpdg/                  # Canonical production package
│   │   ├── api/               # FastAPI app, schemas, routes
│   │   ├── config/            # Constants (weeks, strategies, paths)
│   │   ├── data/              # Telemetry and gateway master loaders
│   │   ├── exceptions.py
│   │   └── ranking/           # V1, V2, Baseline, RankingService, interfaces
│   ├── services/              # Legacy compatibility shims → delegate to src.lpdg
│   ├── part1/                 # Legacy Part 1 pipeline modules
│   └── api/                   # Legacy FastAPI app (uses src.services)
├── tests/
│   ├── test_api.py
│   ├── test_part1.py
│   ├── test_v2_probabilistic.py
│   ├── test_regression_coverage.py
│   └── regression/
│       └── test_frozen_outputs.py   # Cell-by-cell + hash checks
├── docs/
│   ├── architecture.md
│   ├── methodology.md
│   ├── runbook.md
│   └── limitations.md
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/ci.yml
```

---

## API

```powershell
venv\Scripts\python -m uvicorn src.api.app:app --reload
# http://localhost:8000/docs
```

Key endpoints:
- `GET /health`
- `GET /predictions/{week_start}` — top-15 for a given Monday
- `GET /predictions/{week_start}/explain/{gateway_id}` — score breakdown

See [`docs/api.md`](docs/api.md) and [`docs/runbook.md`](docs/runbook.md).

---

## Docker

```powershell
docker build -t lpdg-ranking .
docker-compose up --build
```

The image mounts `./data` as a read-only volume — data is not bundled.

---

## Known Limitations

See [`docs/limitations.md`](docs/limitations.md) for a full discussion.
Key points:

- Field visit outcomes are historically **biased labels** — a gateway could only
  be confirmed by an engineer if it was already ranked highly.
- V2's economic score is based on **assumed cost parameters**, not empirical data.
- Neither strategy was trained on supervised labels — both are evidence-based.
- The 8-week evaluation window is too short for statistically significant
  strategy comparison.

---

## Project Status

| Phase | Status |
|-------|--------|
| Part 1 — Gateway Ranking | ✅ Complete, frozen |
| Phase 1 — Software Development | ✅ Complete |
| Phase 2 — Probabilistic V2 | ✅ Complete |
| Architecture Refactor | ✅ Complete |
| Docker / CI | ✅ Complete |
| Documentation | ✅ Complete |

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [`docs/architecture.md`](docs/architecture.md) | Package layout and design decisions |
| [`docs/methodology.md`](docs/methodology.md) | Algorithm detail for V1, V2, Baseline |
| [`docs/runbook.md`](docs/runbook.md) | How to run, reproduce, test |
| [`docs/limitations.md`](docs/limitations.md) | Known limitations and failure modes |
| [`docs/api.md`](docs/api.md) | REST API specification |
| [`DECISIONS.md`](DECISIONS.md) | Decision log |
| [`AI-USAGE.md`](AI-USAGE.md) | AI assistance disclosure |
