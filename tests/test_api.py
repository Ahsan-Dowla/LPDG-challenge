"""Comprehensive API and End-to-End Test Suite for Gateway Prioritization Service."""

from __future__ import annotations

import datetime as dt
import pytest
from fastapi.testclient import TestClient

from src.api.app import app, create_app
from src.part1.config import SCORED_WEEKS
from src.services.exceptions import PipelineExecutionError
from src.services.interfaces import BaseRanker
from src.services.ranking_service import RankingService


@pytest.fixture
def client() -> TestClient:
    """Default client connected to production application."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Health Check Endpoint Tests
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    """GET /health must return 200 with status ok and not invoke heavy pipeline."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. Prediction Endpoints Tests (GET /predictions/{week})
# ---------------------------------------------------------------------------


def test_predictions_valid_week_returns_15_gateways(client: TestClient) -> None:
    """GET /predictions/{week} must return exactly 15 gateways for a scored week."""
    week = SCORED_WEEKS[0].isoformat()
    response = client.get(f"/predictions/{week}")
    assert response.status_code == 200

    data = response.json()
    assert data["week_start"] == week
    assert data["count"] == 15
    assert len(data["predictions"]) == 15

    ranks = [item["rank"] for item in data["predictions"]]
    assert ranks == list(range(1, 16))


def test_predictions_schema_compliance(client: TestClient) -> None:
    """Predictions must strictly adhere to the defined schema."""
    week = SCORED_WEEKS[-1].isoformat()
    response = client.get(f"/predictions/{week}")
    assert response.status_code == 200

    data = response.json()
    for item in data["predictions"]:
        assert item["week_start"] == week
        assert isinstance(item["rank"], int) and 1 <= item["rank"] <= 15
        assert isinstance(item["gateway_id"], str) and len(item["gateway_id"]) == 12
        assert isinstance(item["score"], (int, float))
        assert isinstance(item["reason"], str) and 0 < len(item["reason"]) <= 300


def test_predictions_across_all_scored_weeks(client: TestClient) -> None:
    """Verify that every scored week produces 15 valid ranked gateways."""
    for monday in SCORED_WEEKS:
        resp = client.get(f"/predictions/{monday.isoformat()}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 15
        assert len(body["predictions"]) == 15


def test_predictions_invalid_date_format(client: TestClient) -> None:
    """Non-ISO date string must return 400 Bad Request."""
    response = client.get("/predictions/not-a-date")
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Invalid date format" in data["detail"]


def test_predictions_out_of_window_week(client: TestClient) -> None:
    """Valid date not in scored window must return 400 Bad Request."""
    response = client.get("/predictions/2026-01-01")
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "not a scored prediction week" in data["detail"]


# ---------------------------------------------------------------------------
# 3. Gateway Explanation Tests (GET /gateways/{gateway_id})
# ---------------------------------------------------------------------------


def test_explain_gateway_success(client: TestClient) -> None:
    """Known gateway returns calculated evidence, rank, and operational details."""
    week = SCORED_WEEKS[0].isoformat()
    preds = client.get(f"/predictions/{week}").json()["predictions"]
    top_gw = preds[0]["gateway_id"]

    response = client.get(f"/gateways/{top_gw}?week={week}")
    assert response.status_code == 200

    data = response.json()
    assert data["gateway_id"] == top_gw
    assert data["week_start"] == week
    assert data["rank"] == 1
    assert data["overall_rank"] == 1
    assert data["score"] == preds[0]["score"]
    assert data["reason"] == preds[0]["reason"]

    details = data["details"]
    assert details["coverage_hours"] > 0
    assert details["problem_hours"] >= 0
    assert details["silent_hours"] >= 0
    assert details["expected_hours"] == 168
    assert details["n_meters_installed"] >= 0
    assert 0 <= details["persistence_pct"] <= 100
    assert details["worst_signal"] in ("offline_duration_sec", "disconnection_cnt")


def test_explain_gateway_colon_separated_id(client: TestClient) -> None:
    """Colon-separated gateway ID is automatically normalized."""
    week = SCORED_WEEKS[0].isoformat()
    preds = client.get(f"/predictions/{week}").json()["predictions"]
    top_gw = preds[0]["gateway_id"]
    # Convert "02423E0E6E9F" -> "02:42:3E:0E:6E:9F"
    colon_id = ":".join(top_gw[i : i + 2] for i in range(0, 12, 2))

    response = client.get(f"/gateways/{colon_id}?week={week}")
    assert response.status_code == 200
    assert response.json()["gateway_id"] == top_gw


def test_explain_gateway_unknown_id_returns_404(client: TestClient) -> None:
    """Unknown gateway returns 404 with structured JSON error."""
    response = client.get("/gateways/UNKNOWN00000?week=2026-02-02")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_explain_gateway_invalid_week_returns_400(client: TestClient) -> None:
    """Invalid week parameter in gateway explanation returns 400."""
    response = client.get("/gateways/02423E0E6E9F?week=bad-week")
    assert response.status_code == 400
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# 4. Trigger Prediction Endpoint Tests (POST /predict)
# ---------------------------------------------------------------------------


def test_post_predict_single_week(client: TestClient) -> None:
    """POST /predict for a single week returns execution summary and 15 predictions."""
    target_week = SCORED_WEEKS[1].isoformat()
    response = client.post("/predict", json={"week_start": target_week})
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["strategy"] == "optimized"
    assert data["weeks_predicted"] == [target_week]
    assert data["total_predictions"] == 15
    assert len(data["predictions"]) == 15


def test_post_predict_all_weeks(client: TestClient) -> None:
    """POST /predict without parameters reruns all 8 scored weeks."""
    response = client.post("/predict")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["total_predictions"] == 120
    assert len(data["weeks_predicted"]) == 8


def test_post_predict_invalid_week(client: TestClient) -> None:
    """POST /predict with invalid week returns 400."""
    response = client.post("/predict", json={"week_start": "2026-99-99"})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_post_predict_malformed_payload(client: TestClient) -> None:
    """POST /predict with invalid JSON structure returns 422."""
    response = client.post("/predict", json={"unexpected_field": 123})
    assert response.status_code == 422
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# 5. Error Handling & Controlled 500 Responses
# ---------------------------------------------------------------------------


class FailingRanker:
    """Mock ranker that raises an internal error."""

    name = "failing"

    def rank_week(self, *args, **kwargs):
        raise PipelineExecutionError("Numerical divergence in rank calculation")

    def predict_week(self, *args, **kwargs):
        raise PipelineExecutionError("Numerical divergence in rank calculation")

    def predict_all(self, *args, **kwargs):
        raise PipelineExecutionError("Pipeline crashed unexpectedly")

    def explain_gateway(self, *args, **kwargs):
        raise PipelineExecutionError("Cannot calculate explanation")


def test_controlled_500_error_no_stack_trace_leakage() -> None:
    """Internal failure must return HTTP 500 JSON without exposing tracebacks or file paths."""
    service = RankingService(ranker=FailingRanker())
    test_app = create_app(service=service)
    custom_client = TestClient(test_app)

    response = custom_client.get("/predictions/2026-02-02")
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    # Traceback indicators must not be present in user-facing response
    assert "Traceback" not in data["detail"]
    assert 'File "' not in data["detail"]


# ---------------------------------------------------------------------------
# 6. End-to-End Pipeline Integration Test
# ---------------------------------------------------------------------------


def test_end_to_end_real_pipeline_flow(client: TestClient) -> None:
    """Full end-to-end flow: POST /predict -> GET /predictions -> GET /gateways.

    Exercises the entire real application path from HTTP API down to real
    telemetry, eligibility filtering, and Optimization V1 scoring without mocks.
    """
    # 1. Health check
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    # 2. Trigger prediction rerun for week 2026-03-23
    test_week = "2026-03-23"
    predict_resp = client.post("/predict", json={"week_start": test_week})
    assert predict_resp.status_code == 200
    predict_data = predict_resp.json()
    assert predict_data["status"] == "success"
    assert predict_data["total_predictions"] == 15

    # 3. Fetch predictions via GET endpoint
    query_resp = client.get(f"/predictions/{test_week}")
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert query_data["count"] == 15

    # 4. Verify exact match between POST /predict and GET /predictions
    post_top1 = predict_data["predictions"][0]
    get_top1 = query_data["predictions"][0]
    assert post_top1["gateway_id"] == get_top1["gateway_id"]
    assert post_top1["score"] == get_top1["score"]
    assert post_top1["reason"] == get_top1["reason"]

    # 5. Drill into top gateway via GET /gateways/{gateway_id}
    top_id = post_top1["gateway_id"]
    explain_resp = client.get(f"/gateways/{top_id}?week={test_week}")
    assert explain_resp.status_code == 200
    explain_data = explain_resp.json()

    assert explain_data["gateway_id"] == top_id
    assert explain_data["week_start"] == test_week
    assert explain_data["rank"] == 1
    assert explain_data["score"] == post_top1["score"]
    assert explain_data["reason"] == post_top1["reason"]
    assert explain_data["details"]["coverage_hours"] > 0
