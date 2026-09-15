# Gateway Prioritization API Documentation

Phase 1 Software Development layer providing a clean REST API interface around the Part 1 gateway-ranking pipeline.

The API exposes endpoints to query weekly predictions, explain individual gateway rankings based on operational telemetry evidence, and trigger prediction reruns.

---

## 1. Application Architecture

The application implements a decoupled, layered architecture to isolate web routing from ranking logic:

```
Client (HTTP / Tests / CLI)
          │
          ▼
   FastAPI Layer (`src/api/`)
   - `routes.py`: Endpoint handlers (/health, /predictions, /predictions/{week}/explain/{gw}, /gateways, /run, /predict)
   - `schemas.py`: Pydantic models enforcing payload validation and contracts
   - `app.py`: Factory, dependency injection, and centralized exception handling
          │
          ▼
   Service Layer (`src/services/`)
   - `ranking_service.py`: Orchestrates dataset loading, caching, and input validation
   - `exceptions.py`: Domain-specific exceptions (GatewayNotFoundError, InvalidWeekError)
          │
          ▼
   Ranker Abstraction (`src/services/interfaces.py`)
   - `BaseRanker` Protocol defining `rank_week`, `predict_week`, `predict_all`, `explain_gateway`
          │
          ▼
   Ranker Adapter (`src/services/v1_ranker.py`)
   - `V1OptimizedRanker`: Pluggable adapter wrapping the Part 1 core algorithm
          │
          ▼
   Frozen Part 1 Pipeline (`src/part1/`)
   - `ranker_optimized.py`: Severity, persistence, corroboration, and exposure logic
   - `eligibility.py`: Cutoff and decommissioning filtering
   - `data_loader.py`: Telemetry and master dataset ingestion
```

### Architectural Principles
1. **API Independence**: The API routes and schemas have zero awareness of the underlying scoring formula or metric weights.
2. **Swappable Implementation**: Future Part 2 probabilistic models or ML rankers can be introduced by implementing `BaseRanker` without altering any API route code.
3. **Core Stability**: The frozen Part 1 ranking pipeline remains completely isolated from API concerns.
4. **Information Hiding**: Internal server exceptions and filesystem paths are caught and transformed into clean, deterministic JSON errors.

---

## 2. Getting Started

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

## 3. API Endpoints

### 3.1 Health Check
**`GET /health`**

- **Purpose**: Determines if the service is operational and accessible.
- **Behavior**: Responds immediately without running expensive data loading or ranking pipelines.
- **Request**: No parameters.
- **Response `200 OK`**:
```json
{
  "status": "ok"
}
```
- **Error Cases**: Returns `500 Internal Server Error` if an unhandled service failure occurs.

---

### 3.2 Get Weekly Predictions
**`GET /predictions/{week}`**

- **Purpose**: Returns the 15 recommended gateway visits for a specific scored Monday cutoff.
- **Request Parameters**:
  - `week` *(path parameter, string)*: Scored Monday cutoff in `YYYY-MM-DD` format.
- **Scored Weeks Supported**:
  `2026-02-02`, `2026-02-09`, `2026-02-16`, `2026-02-23`, `2026-03-02`, `2026-03-09`, `2026-03-16`, `2026-03-23`.
- **Response `200 OK`**:
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
- **Error Cases**:
  - `400 Bad Request`: If `{week}` is not formatted as `YYYY-MM-DD` (`"Invalid date format 'not-a-date'. Expected YYYY-MM-DD."`).
  - `400 Bad Request`: If `{week}` is a valid date but outside the scored evaluation window (`"Week '2026-01-01' is not a scored prediction week."`).
  - `500 Internal Server Error`: If telemetry data is missing or calculation fails.

---

### 3.3 Explain Gateway Ranking
**`GET /gateways/{gateway_id}`**

- **Purpose**: Explains why a gateway is ranked at its position using real calculated operational fields.
- **Request Parameters**:
  - `gateway_id` *(path parameter, string)*: 12-character hex ID (`02423E0E6E9F`) or colon-separated MAC (`02:42:3E:0E:6E:9F`).
  - `week` *(optional query parameter, string)*: Scored Monday cutoff (`YYYY-MM-DD`). Defaults to the latest scored week (`2026-03-23`).
- **Response `200 OK`**:
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
- **Error Cases**:
  - `404 Not Found`: Gateway ID does not exist in the active/evaluated pool for that week (`{"detail": "Gateway 'XYZ' not found in evaluated active set for week 2026-02-02"}`).
  - `400 Bad Request`: If `week` query parameter is invalid or out of window.
  - `400 Bad Request`: If `gateway_id` is empty.

---

### 3.4 Explain Gateway Ranking by Week Cutoff
**`GET /predictions/{week_start}/explain/{gateway_id}`**

- **Purpose**: Explains why a gateway is ranked at its position for a specific Monday cutoff week.
- **Request Parameters**:
  - `week_start` *(path parameter, string)*: Scored Monday cutoff (`YYYY-MM-DD`).
  - `gateway_id` *(path parameter, string)*: 12-character hex ID (`02423E0E6E9F`) or colon-separated MAC.
- **Response `200 OK`**:
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
- **Error Cases**:
  - `400 Bad Request`: If `week_start` is not a valid scored prediction week.
  - `404 Not Found`: If `gateway_id` was not found in the evaluated active set for that week.

---

### 3.5 Run Prediction Pipeline on Fresh Data
**`POST /run`**

- **Purpose**: Rereads fresh telemetry dropped into the mounted `data/` volume and reruns the ranking pipeline without requiring a container restart.
- **Behavior**: Flushes cached data in memory, reads updated files from disk, re-evaluates all 8 scored weeks, and returns the top 15 recommendations for each week.
- **Request Body**: None.
- **Response `200 OK`**:
```json
{
  "status": "success",
  "strategy": "v1",
  "weeks_predicted": [
    "2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23",
    "2026-03-02", "2026-03-09", "2026-03-16", "2026-03-23"
  ],
  "total_predictions": 120,
  "predictions": [
    {
      "week_start": "2026-02-02",
      "rank": 1,
      "gateway_id": "02423E0E6E9F",
      "score": 1.5913,
      "reason": "Optimized V1: 77/77h observed impaired..."
    }
  ]
}
```
- **Error Cases**:
  - `500 Internal Server Error`: If data directory is unreadable or calculation fails.

---

### 3.6 Trigger Prediction Rerun (Ad-hoc / Parameterized)
**`POST /predict`**

- **Purpose**: Explicitly reruns the prediction pipeline.
- **Request Body (Optional)**:
```json
{
  "week_start": "2026-03-23",
  "output_path": "predictions.csv"
}
```
  - `week_start` *(optional)*: Specific Monday cutoff to rerun. If omitted, reruns all 8 scored weeks.
  - `output_path` *(optional)*: File destination to write predictions CSV.
- **Response `200 OK`**:
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
- **Error Cases**:
  - `400 Bad Request`: If `week_start` is not a valid scored prediction week.
  - `422 Unprocessable Entity`: If unexpected payload fields are submitted.
  - `500 Internal Server Error`: If pipeline execution fails during recalculation.

---

## 4. Error Handling Summary

All endpoints return structured JSON errors with HTTP status codes matching standard REST semantics:

| HTTP Status | Trigger Condition | Example Response |
|---|---|---|
| **400 Bad Request** | Unparseable date or unscored week requested | `{"detail": "Week '2026-01-01' is not a scored prediction week."}` |
| **404 Not Found** | Gateway not found in evaluated active set | `{"detail": "Gateway 'UNKNOWN' not found in evaluated active set for week 2026-02-02"}` |
| **422 Unprocessable Entity** | Malformed JSON schema or extra fields | `{"detail": "Request validation failed: Extra inputs are not permitted"}` |
| **500 Internal Server Error** | Missing data files or internal calculation failure | `{"detail": "Ranking pipeline failed: ..."}` |

---

## 5. Running Automated Tests

Run the full pytest suite (34 passing tests):
```powershell
venv\Scripts\python.exe -m pytest -q
```

Run specific test modules:
```powershell
# API and E2E tests (16 tests)
venv\Scripts\python.exe -m pytest tests/test_api.py -v

# Persistence/coverage regression test (1 test)
venv\Scripts\python.exe -m pytest tests/test_regression_coverage.py -v

# Core Part 1 unit & pipeline tests (17 tests)
venv\Scripts\python.exe -m pytest tests/test_part1.py -v
```
