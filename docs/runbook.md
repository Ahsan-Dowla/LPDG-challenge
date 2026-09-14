# Runbook

## Prerequisites

- Python 3.13+
- Git
- (Optional) Docker 29+

Install dependencies:
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Produce Official Predictions

### V1 — Part 1 Official Submission
```powershell
venv\Scripts\python main.py
# writes predictions.csv (120 rows, 8 weeks)
```

Or via the scripts entrypoint:
```powershell
venv\Scripts\python scripts\predict.py
# writes outputs\predictions.csv
```

### V2 — Part 2 Probabilistic (Challenger)
```powershell
venv\Scripts\python main.py --strategy v2 --out predictions_v2.csv
```

Or:
```powershell
venv\Scripts\python scripts\predict.py --strategy v2
# writes outputs\predictions_v2.csv
```

### Baseline
```powershell
venv\Scripts\python scripts\predict.py --strategy baseline
# writes outputs\predictions_baseline.csv
```

---

## Validate Submission Format
```powershell
venv\Scripts\python validate_submission.py predictions.csv
venv\Scripts\python validate_submission.py predictions_v2.csv
```

---

## Run Tests
```powershell
# Full suite (all 45 tests + regression)
venv\Scripts\python -m pytest -q

# Regression tests only
venv\Scripts\python -m pytest tests/regression/ -v

# Unit / integration tests only
venv\Scripts\python -m pytest tests/test_part1.py tests/test_v2_probabilistic.py -v
```

---

## Run Walk-Forward Backtest
```powershell
# V1 backtest — verify 15/15 overlap with frozen reference
venv\Scripts\python scripts\backtest.py --ref predictions.csv

# V2 backtest
venv\Scripts\python scripts\backtest.py --strategy v2 --ref predictions_v2.csv
```

---

## Start the REST API
```powershell
venv\Scripts\python -m uvicorn src.api.app:app --reload
# API runs at http://localhost:8000
# Docs at  http://localhost:8000/docs
```

Key endpoints:
- `GET /health` — liveness check
- `GET /predictions/{week_start}` — top-15 for a given Monday (YYYY-MM-DD)
- `GET /predictions/{week_start}/explain/{gateway_id}` — detailed explanation

---

## Docker
```powershell
# Build
docker build -t lpdg-ranking .

# Run
docker run -p 8000:8000 -v ${PWD}/data:/app/data lpdg-ranking

# Compose
docker-compose up --build
```

---

## Verify Frozen Hash Integrity
```powershell
venv\Scripts\python -c "
import hashlib, sys
h = hashlib.sha256(open('predictions.csv','rb').read()).hexdigest().upper()
ref = '0F4D38C524EE8E224D321E6381A5CEF83BFC81EF4D0E9C2B466C8B402125F6D0'
print('OK' if h == ref else f'MISMATCH: {h}')
"
```

---

## Data Directory Layout

```
data/
  gateway_master.csv         # Gateway metadata (installed_on, decommissioned_on, n_meters)
  telemetry/                 # Parquet partition by date
  engineer_reviews.csv       # (evaluation target — never used as prediction feature)
  meter_read_success.csv     # (evaluation target — never used as prediction feature)
  field_visit_outcomes.csv   # (optional, for evaluate.py)
```

> **Important**: `engineer_reviews.csv` and `meter_read_success.csv` are evaluation
> targets only. They must never be used as input features to any ranker.
