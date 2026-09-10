# Gateway Prioritization API Documentation

Phase 1 Software Development layer providing a clean REST API interface around the Part 1 gateway-ranking pipeline.

The API exposes endpoints to query weekly predictions, explain individual gateway rankings based on operational telemetry evidence, and trigger prediction reruns.

---

## 1. Getting Started

### Prerequisites
- Python 3.11+
- Virtual environment with project dependencies installed:
  ```bash
  pip install -r requirements.txt
  ```

### Starting the API Server
Start the service using `uvicorn`:

```bash
# Standard development startup
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Or using the virtual environment interpreter directly on Windows:
```powershell
.\venv\Scripts\uvicorn.exe src.api.app:app --host 127.0.0.1 --port 8000
```

Once running, the interactive OpenAPI documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 2. API Endpoints

### 2.1 Health Check
**`GET /health`**

Determines if the service is alive and accessible. This endpoint responds immediately without running expensive data loading or ranking pipelines.

**Response `200 OK`**:
```json
{
  "status": "ok"
}
```

---

### 2.2 Get Weekly Predictions
**`GET /predictions/{week}`**

Returns the 15 recommended gateway visits for a specific scored Monday cutoff (`YYYY-MM-DD`).

**Scored Weeks Supported:**
- `2026-02-02`
- `2026-02-09`
- `2026-02-16`
- `2026-02-23`
- `2026-03-02`
- `2026-03-09`
- `2026-03-16`
- `2026-03-23`

**Example Request:**
```bash
curl -X GET "http://127.0.0.1:8000/predictions/2026-03-23"
```

**Response `200 OK`**:
```json
{
  "week_start": "2026-03-23",
  "count": 15,
  "predictions": [
    {
      "week_start": "2026-03-23",
      "rank": 1,
      "gateway_id": "02423E0E6E9F",
      "score": 1.5913,
      "reason": "Optimized V1: 77/77h observed impaired (offline_duration_sec), 91h silent of 168h expected; 297 meters exposed; score=1.5913."
    },
    {
      "week_start": "2026-03-23",
      "rank": 2,
      "gateway_id": "024213197E3E",
      "score": 1.4821,
      "reason": "Optimized V1: 65/65h observed impaired (offline_duration_sec), 103h silent of 168h expected; 180 meters exposed; score=1.4821."
    }
  ]
}
```

---

### 2.3 Explain Gateway Ranking
**`GET /gateways/{gateway_id}`**

Explains why a gateway is ranked at its position for a given week using real operational telemetry evidence. Accepts both compact 12-character hex IDs (`02423E0E6E9F`) and colon-separated MAC-style IDs (`02:42:3E:0E:6E:9F`).

**Query Parameters:**
- `week` *(optional, string)*: Scored Monday cutoff (`YYYY-MM-DD`). Defaults to the latest scored week (`2026-03-23`).

**Example Request:**
```bash
curl -X GET "http://127.0.0.1:8000/gateways/02423E0E6E9F?week=2026-02-02"
```

**Response `200 OK`**:
```json
{
  "gateway_id": "02423E0E6E9F",
  "week_start": "2026-02-02",
  "rank": 1,
  "overall_rank": 1,
  "score": 1.5913,
  "reason": "Optimized V1: 77/77h observed impaired (offline_duration_sec), 91h silent of 168h expected; 297 meters exposed; score=1.5913.",
  "details": {
    "coverage_hours": 77,
    "problem_hours": 77,
    "silent_hours": 91,
    "expected_hours": 168,
    "worst_signal": "offline_duration_sec",
    "n_meters_installed": 297,
    "persistence_pct": 46
  }
}
```

**If Gateway is Not Found (`404 Not Found`):**
```json
{
  "detail": "Gateway 'UNKNOWN' not found in evaluated active set for week 2026-02-02"
}
```

---

### 2.4 Trigger Prediction Rerun
**`POST /predict`**

Reruns the prediction pipeline. Can rerun either a single specified week or all 8 scored weeks.

**Request Body (Optional):**
```json
{
  "week_start": "2026-03-23",
  "output_path": "predictions.csv"
}
```

- If `week_start` is omitted, all 8 scored weeks are evaluated.
- If `output_path` is specified, results are safely written to that CSV file.

**Example Request:**
```bash
curl -X POST "http://127.0.0.1:8000/predict" \
     -H "Content-Type: application/json" \
     -d '{"week_start": "2026-03-23"}'
```

**Response `200 OK`**:
```json
{
  "status": "success",
  "strategy": "optimized",
  "weeks_predicted": [
    "2026-03-23"
  ],
  "total_predictions": 15,
  "output_path": null,
  "predictions": [
    {
      "week_start": "2026-03-23",
      "rank": 1,
      "gateway_id": "02423E0E6E9F",
      "score": 1.5913,
      "reason": "Optimized V1: 77/77h observed impaired (offline_duration_sec), 91h silent of 168h expected; 297 meters exposed; score=1.5913."
    }
  ]
}
```

---

## 3. Error Handling

The API uses standard HTTP status codes with human-readable, deterministic JSON responses. Internal server paths and tracebacks are never exposed to clients.

| HTTP Status | Condition | Example Response |
|---|---|---|
| **400 Bad Request** | Unparseable date or unscored week requested | `{"detail": "Week '2026-01-01' is not a scored prediction week. Scored weeks are: [...]"}` |
| **404 Not Found** | Gateway not in active/evaluated pool | `{"detail": "Gateway 'XYZ' not found in evaluated active set for week 2026-02-02"}` |
| **422 Unprocessable Entity** | Malformed JSON or invalid schema field types | `{"detail": "Request validation failed: Field required"}` |
| **500 Internal Server Error** | Internal pipeline or data loading error | `{"detail": "Prediction pipeline failure: ..."}` |

---

## 4. Running Tests

Run the full pytest suite (including API tests, Part 1 baseline tests, and regression tests):

```bash
pytest -v
```

Run only API tests:
```bash
pytest tests/test_api.py -v
```

Run regression tests:
```bash
pytest tests/test_regression_coverage.py -v
```

Run the existing Part 1 CLI pipeline:
```bash
python main.py --data data --out predictions.csv
```

Validate predictions with the official grader validator:
```bash
python validate_submission.py predictions.csv
```
