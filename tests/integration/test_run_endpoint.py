"""Integration tests for POST /run endpoint.

Verifies:
- Initial /run succeeds and returns valid predictions.
- Calling /run twice returns consistent results (idempotent).
- /run flushes cached data and rereads from the mounted directory.
- Missing data returns a controlled 500 error (no traceback leakage).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.lpdg.config.settings import STRATEGY_V1
from src.services.ranking_service import RankingService


SCORED_WEEKS = [
    "2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23",
    "2026-03-02", "2026-03-09", "2026-03-16", "2026-03-23",
]


@pytest.fixture
def client() -> TestClient:
    """Default client connected to production application."""
    from src.api.app import app
    return TestClient(app)


@pytest.fixture
def fresh_client(synthetic_data_dir: Path, tmp_path: Path) -> TestClient:
    """Client with a freshly instantiated service pointing to a mutable copy of synthetic data."""
    # Copy synthetic fixture to tmp_path so cache flushing/file dropping tests are isolated
    isolated_data = tmp_path / "data"
    shutil.copytree(synthetic_data_dir, isolated_data)
    service = RankingService(strategy=STRATEGY_V1, data_dir=isolated_data)
    app = create_app(service=service)
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. POST /run — initial run succeeds
# ---------------------------------------------------------------------------

def test_run_initial_success(fresh_client: TestClient) -> None:
    """POST /run succeeds and returns 120 predictions across 8 weeks."""
    response = fresh_client.post("/run")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["status"] == "success"
    assert data["strategy"] in ("optimized", "v1")
    assert len(data["weeks_predicted"]) == 8
    assert set(data["weeks_predicted"]) == set(SCORED_WEEKS)
    assert data["total_predictions"] == 120
    assert len(data["predictions"]) == 120


# ---------------------------------------------------------------------------
# 2. POST /run — second call returns consistent results (no duplication)
# ---------------------------------------------------------------------------

def test_run_idempotent(fresh_client: TestClient) -> None:
    """Calling POST /run twice returns the same 120 predictions each time."""
    r1 = fresh_client.post("/run")
    r2 = fresh_client.post("/run")

    assert r1.status_code == 200
    assert r2.status_code == 200

    d1 = r1.json()
    d2 = r2.json()

    assert d1["total_predictions"] == d2["total_predictions"] == 120

    # Rows should be identical (deterministic ranking)
    preds1 = sorted(d1["predictions"], key=lambda x: (x["week_start"], x["rank"]))
    preds2 = sorted(d2["predictions"], key=lambda x: (x["week_start"], x["rank"]))
    assert preds1 == preds2, "Second /run returned different predictions — non-deterministic!"


# ---------------------------------------------------------------------------
# 3. POST /run — rereads mounted data (cache flush verified via mock)
# ---------------------------------------------------------------------------

def test_run_flushes_cache(fresh_client: TestClient) -> None:
    """POST /run calls reload_data() before running predictions."""
    # Warm up the cache by calling /health first
    fresh_client.get("/health")

    reload_calls: list[str] = []
    original_reload = RankingService.reload_data

    def tracking_reload(self: RankingService) -> None:
        reload_calls.append("reload_data called")
        original_reload(self)

    with patch.object(RankingService, "reload_data", tracking_reload):
        response = fresh_client.post("/run")

    assert response.status_code == 200
    assert len(reload_calls) >= 1, "reload_data() was not called by POST /run"


# ---------------------------------------------------------------------------
# 4. POST /run — missing data returns structured 500 error
# ---------------------------------------------------------------------------

def test_run_missing_data_returns_controlled_error() -> None:
    """POST /run with a non-existent data directory returns 500 with JSON detail."""
    service = RankingService(
        strategy=STRATEGY_V1,
        data_dir=Path("/nonexistent/lpdg_data_that_cannot_exist"),
    )
    app = create_app(service=service)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/run")

    assert response.status_code == 500, f"Expected 500 but got {response.status_code}"
    body = response.json()
    assert "detail" in body, "Error response missing 'detail' field"
    # Must NOT leak Python tracebacks or raw exception types
    assert "<traceback>" not in body["detail"]
    assert "Traceback" not in body["detail"]


# ---------------------------------------------------------------------------
# 5. GET /predictions/{week_start}/explain/{gateway_id}
# ---------------------------------------------------------------------------

def test_explain_by_week_path_endpoint(fresh_client: TestClient) -> None:
    """GET /predictions/{week_start}/explain/{gateway_id} returns explanation."""
    week = "2026-02-02"
    preds = fresh_client.get(f"/predictions/{week}").json()["predictions"]
    top_gw = preds[0]["gateway_id"]

    response = fresh_client.get(f"/predictions/{week}/explain/{top_gw}")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["gateway_id"] == top_gw
    assert data["week_start"] == week
    assert data["rank"] == 1
    assert data["overall_rank"] == 1
    assert isinstance(data["score"], float)
    assert isinstance(data["reason"], str)
    assert isinstance(data["details"], dict)


def test_explain_by_week_invalid_gateway_returns_404(fresh_client: TestClient) -> None:
    """GET /predictions/{week_start}/explain/{gateway_id} with unknown gateway returns 404."""
    response = fresh_client.get("/predictions/2026-02-02/explain/DOESNOTEXIST0")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_explain_by_week_invalid_week_returns_400(fresh_client: TestClient) -> None:
    """GET /predictions/{week_start}/explain/{gateway_id} with invalid week returns 400."""
    response = fresh_client.get("/predictions/not-a-date/explain/AABBCCDDEE11")
    assert response.status_code == 400
    assert "detail" in response.json()
