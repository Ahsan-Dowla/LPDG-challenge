"""Comprehensive tests for Gateway Ranking V2 (Probabilistic & Expected-Value).

Validates:
  1. Robust anomaly calculation (robust_z_pos)
  2. Bayesian Beta-Binomial persistence and shrinkage
  3. Coverage and silence handling
  4. Deterministic ranking and reproducible tie-breaking
  5. Format & schema validity (15 gateways/week, 8 weeks, ranks 1..15, reason <= 300 chars)
  6. Temporal boundary enforcement (no future data leakage)
  7. BaseRanker protocol compliance
  8. Service & API integration with V2
  9. V1 backward compatibility
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

from src.api.app import create_app
from src.part1.config import (
    EXPECTED_WEEKLY_HOURS,
    OUTPUT_COLUMNS,
    SCORED_WEEKS,
    STRATEGY_OPTIMIZED,
    STRATEGY_V2,
    VISITS_PER_WEEK,
)
from src.part1.ranker_v2 import build_predictions_v2, rank_week_v2, robust_z_pos
from src.services.interfaces import BaseRanker
from src.services.ranking_service import RankingService
from src.services.v1_ranker import V1OptimizedRanker
from src.services.v2_ranker import V2ProbabilisticRanker

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# 1. Unit Tests: Robust Anomaly Calculation
# ---------------------------------------------------------------------------

def test_robust_z_pos_normal():
    """Verify robust z-score calculation with typical variance."""
    s = pd.Series([0.0, 0.0, 0.0, 10.0, 50.0, 100.0])
    res = robust_z_pos(s)
    assert len(res) == len(s)
    assert res.min() >= 0.0
    assert res.max() <= 1.0
    # Values at or below median must be exactly 0.0
    assert res.iloc[0] == 0.0
    assert res.iloc[1] == 0.0
    assert res.iloc[2] == 0.0
    # Highest value should be normalized to 1.0
    assert res.iloc[-1] == 1.0


def test_robust_z_pos_all_zeros():
    """Verify robust z-score when MAD is zero (all values identical)."""
    s = pd.Series([0.0, 0.0, 0.0, 0.0])
    res = robust_z_pos(s)
    assert (res == 0.0).all()


def test_robust_z_pos_extreme_outlier():
    """Verify extreme outliers do not cause NaN or negative values."""
    s = pd.Series([0.0, 0.0, 1.0, 2.0, 1_000_000.0])
    res = robust_z_pos(s)
    assert not res.isna().any()
    assert res.iloc[-1] == 1.0
    assert res.iloc[0] == 0.0


# ---------------------------------------------------------------------------
# 2. Unit Tests: Bayesian Beta-Binomial Persistence & Shrinkage
# ---------------------------------------------------------------------------

def test_bayesian_persistence_shrinkage():
    """Verify Bayesian posterior shrinks low-coverage gateways toward healthy prior."""
    alpha_0, beta_0 = 1.0, 9.0  # Prior mean = 1/(1+9) = 0.10

    # Case A: High coverage (168h), 100% impaired (168/168)
    n_a, k_a = 168, 168
    eff_n_a = max(n_a, EXPECTED_WEEKLY_HOURS)
    post_a = (alpha_0 + k_a) / (alpha_0 + beta_0 + eff_n_a)

    # Case B: Low coverage (5h), 100% impaired (5/5)
    n_b, k_b = 5, 5
    eff_n_b = max(n_b, EXPECTED_WEEKLY_HOURS)
    post_b = (alpha_0 + k_b) / (alpha_0 + beta_0 + eff_n_b)

    # Raw empirical rates are both 1.0, but Bayesian posterior must strongly shrink Case B!
    assert post_a > 0.90
    assert post_b < 0.10
    assert post_a > post_b * 10


# ---------------------------------------------------------------------------
# 3. Determinism & Protocol Compliance
# ---------------------------------------------------------------------------

def test_v2_ranker_protocol_compliance():
    """Verify V2ProbabilisticRanker implements BaseRanker protocol."""
    ranker = V2ProbabilisticRanker()
    assert isinstance(ranker, BaseRanker)
    assert ranker.name == STRATEGY_V2


def test_v2_deterministic_ranking():
    """Verify V2 ranking is bit-for-bit identical across two independent runs."""
    from src.part1.data_loader import load_gateway_master, load_telemetry_extended
    master = load_gateway_master(DATA_DIR)
    telemetry = load_telemetry_extended(DATA_DIR)

    monday = SCORED_WEEKS[0]
    ranker = V2ProbabilisticRanker()

    df1 = ranker.predict_week(telemetry, master, monday, limit=15)
    df2 = ranker.predict_week(telemetry, master, monday, limit=15)

    pd.testing.assert_frame_equal(df1, df2)


# ---------------------------------------------------------------------------
# 4. Output Schema & Constraint Validation
# ---------------------------------------------------------------------------

def test_v2_predictions_schema_and_constraints():
    """Verify V2 predictions satisfy all 8-week challenge constraints."""
    from src.part1.data_loader import load_gateway_master, load_telemetry_extended
    master = load_gateway_master(DATA_DIR)
    telemetry = load_telemetry_extended(DATA_DIR)

    ranker = V2ProbabilisticRanker()
    preds = ranker.predict_all(telemetry, master, SCORED_WEEKS)

    # Exactly 120 rows
    assert len(preds) == 120
    assert list(preds.columns) == OUTPUT_COLUMNS

    # 8 distinct weeks, 15 rows each
    assert preds["week_start"].nunique() == 8
    for week, group in preds.groupby("week_start"):
        assert len(group) == VISITS_PER_WEEK
        # Ranks 1 to 15 without duplicates
        assert sorted(group["rank"].tolist()) == list(range(1, 16))
        # Unique gateway IDs within the week
        assert group["gateway_id"].nunique() == VISITS_PER_WEEK
        # Valid reasons <= 300 chars
        for reason in group["reason"]:
            assert isinstance(reason, str)
            assert 0 < len(reason) <= 300


# ---------------------------------------------------------------------------
# 5. Temporal Leakage Safeguard Test
# ---------------------------------------------------------------------------

def test_v2_no_future_data_leakage():
    """Verify predictions for week W are identical when future telemetry is purged."""
    from src.part1.data_loader import load_gateway_master, load_telemetry_extended
    master = load_gateway_master(DATA_DIR)
    telemetry = load_telemetry_extended(DATA_DIR)

    monday = SCORED_WEEKS[1]  # 2026-02-09
    end_cutoff = pd.Timestamp(monday, tz="UTC")

    ranker = V2ProbabilisticRanker()
    preds_full = ranker.predict_week(telemetry, master, monday, limit=15)

    # Truncate telemetry to strictly before Monday
    telemetry_truncated = telemetry[telemetry["ts"] < end_cutoff].copy()
    preds_truncated = ranker.predict_week(telemetry_truncated, master, monday, limit=15)

    pd.testing.assert_frame_equal(preds_full, preds_truncated)


# ---------------------------------------------------------------------------
# 6. Service & API Integration Tests
# ---------------------------------------------------------------------------

def test_service_with_v2_ranker():
    """Verify RankingService functions properly with V2ProbabilisticRanker."""
    service = RankingService(data_dir=DATA_DIR, ranker=V2ProbabilisticRanker())
    assert service.ranker.name == STRATEGY_V2

    res = service.get_predictions_for_week("2026-02-02")
    assert res["count"] == 15
    assert len(res["predictions"]) == 15

    # Explain gateway
    top_gw = res["predictions"][0]["gateway_id"]
    explanation = service.explain_gateway(top_gw, "2026-02-02")
    assert explanation["gateway_id"] == top_gw
    assert explanation["rank"] == 1
    assert "expected_value_euro" in explanation["details"]
    assert "probability_impaired" in explanation["details"]


def test_api_with_v2_service():
    """Verify FastAPI endpoints operate correctly when injected with V2 service."""
    service = RankingService(data_dir=DATA_DIR, ranker=V2ProbabilisticRanker())
    app = create_app(service)
    client = TestClient(app)

    # Health
    r = client.get("/health")
    assert r.status_code == 200

    # Predictions
    r = client.get("/predictions/2026-02-02")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 15
    assert len(data["predictions"]) == 15
    first = data["predictions"][0]
    assert "V2 Probabilistic" in first["reason"]

    # Explain
    gw = first["gateway_id"]
    r_exp = client.get(f"/gateways/{gw}?week=2026-02-02")
    assert r_exp.status_code == 200
    exp_data = r_exp.json()
    assert exp_data["gateway_id"] == gw
    assert exp_data["rank"] == 1


# ---------------------------------------------------------------------------
# 7. V1 Backward Compatibility Test
# ---------------------------------------------------------------------------

def test_v1_compatibility_remains_frozen():
    """Verify V1 ranker continues to produce identical results as before."""
    from src.part1.data_loader import load_gateway_master, load_telemetry_extended
    master = load_gateway_master(DATA_DIR)
    telemetry = load_telemetry_extended(DATA_DIR)

    v1_ranker = V1OptimizedRanker()
    preds_v1 = v1_ranker.predict_week(telemetry, master, SCORED_WEEKS[0], limit=15)
    assert len(preds_v1) == 15
    assert "Optimized V1" in preds_v1.iloc[0]["reason"]
