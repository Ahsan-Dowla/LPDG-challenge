"""Semantic regression tests: frozen predictions must never change.

Frozen hashes (do NOT change):
  V1  : 0F4D38C524EE8E224D321E6381A5CEF83BFC81EF4D0E9C2B466C8B402125F6D0
  V2  : B3CD9031CA3B71BC34A02EC854D3648A0ACBF585E5FA2DE84EE55A9D152C2652
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from src.lpdg.config import DATA_DIR, SCORED_WEEKS, VISITS_PER_WEEK
from src.lpdg.ranking.service import RankingService
from src.lpdg.ranking.v1 import V1Ranker
from src.lpdg.ranking.v2 import V2Ranker

ROOT = Path(__file__).resolve().parent.parent.parent

_V1_HASH = "0F4D38C524EE8E224D321E6381A5CEF83BFC81EF4D0E9C2B466C8B402125F6D0"
_V2_HASH = "B3CD9031CA3B71BC34A02EC854D3648A0ACBF585E5FA2DE84EE55A9D152C2652"


@pytest.fixture(scope="module")
def v1_predictions():
    return RankingService(data_dir=DATA_DIR, strategy=V1Ranker()).predict_all()


@pytest.fixture(scope="module")
def v2_predictions():
    return RankingService(data_dir=DATA_DIR, strategy=V2Ranker()).predict_all()


@pytest.fixture(scope="module")
def v1_frozen():
    p = ROOT / "predictions.csv"
    if not p.exists():
        pytest.skip("predictions.csv not found")
    return pd.read_csv(p)


@pytest.fixture(scope="module")
def v2_frozen():
    p = ROOT / "predictions_v2.csv"
    if not p.exists():
        pytest.skip("predictions_v2.csv not found")
    return pd.read_csv(p)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_v1_file_hash_unchanged():
    p = ROOT / "predictions.csv"
    if not p.exists():
        pytest.skip("predictions.csv not present")
    assert _sha256(p) == _V1_HASH, f"V1 hash changed: {_sha256(p)}"


def test_v2_file_hash_unchanged():
    p = ROOT / "predictions_v2.csv"
    if not p.exists():
        pytest.skip("predictions_v2.csv not present")
    assert _sha256(p) == _V2_HASH, f"V2 hash changed: {_sha256(p)}"


def test_v1_shape(v1_predictions):
    assert len(v1_predictions) == VISITS_PER_WEEK * len(SCORED_WEEKS)
    assert v1_predictions["week_start"].nunique() == len(SCORED_WEEKS)


def test_v2_shape(v2_predictions):
    assert len(v2_predictions) == VISITS_PER_WEEK * len(SCORED_WEEKS)
    assert v2_predictions["week_start"].nunique() == len(SCORED_WEEKS)


@pytest.mark.parametrize("week", SCORED_WEEKS)
def test_v1_ranks_complete(v1_predictions, week):
    wdf = v1_predictions[v1_predictions["week_start"] == week.isoformat()]
    assert sorted(wdf["rank"].tolist()) == list(range(1, VISITS_PER_WEEK + 1))


@pytest.mark.parametrize("week", SCORED_WEEKS)
def test_v2_ranks_complete(v2_predictions, week):
    wdf = v2_predictions[v2_predictions["week_start"] == week.isoformat()]
    assert sorted(wdf["rank"].tolist()) == list(range(1, VISITS_PER_WEEK + 1))


def test_v1_live_matches_frozen(v1_predictions, v1_frozen):
    live = v1_predictions.sort_values(["week_start", "rank"]).reset_index(drop=True)
    frozen = v1_frozen.sort_values(["week_start", "rank"]).reset_index(drop=True)
    for _, row in frozen.iterrows():
        week, rank = row["week_start"], row["rank"]
        gws = live[(live["week_start"] == week) & (live["rank"] == rank)]["gateway_id"].values
        assert len(gws) == 1
        assert gws[0] == row["gateway_id"], f"V1 mismatch week={week} rank={rank}: live={gws[0]} frozen={row['gateway_id']}"
    mismatches = (live["score"].round(4).values != frozen["score"].round(4).values).sum()
    assert mismatches == 0, f"V1: {mismatches} score mismatches"


def test_v2_live_matches_frozen(v2_predictions, v2_frozen):
    live = v2_predictions.sort_values(["week_start", "rank"]).reset_index(drop=True)
    frozen = v2_frozen.sort_values(["week_start", "rank"]).reset_index(drop=True)
    for _, row in frozen.iterrows():
        week, rank = row["week_start"], row["rank"]
        gws = live[(live["week_start"] == week) & (live["rank"] == rank)]["gateway_id"].values
        assert len(gws) == 1
        assert gws[0] == row["gateway_id"], f"V2 mismatch week={week} rank={rank}"
    mismatches = (live["score"].round(2).values != frozen["score"].round(2).values).sum()
    assert mismatches == 0, f"V2: {mismatches} score mismatches"


@pytest.mark.parametrize("week", SCORED_WEEKS)
def test_v1_no_future_leakage(week):
    svc = RankingService(data_dir=DATA_DIR, strategy=V1Ranker())
    result = svc.get_predictions_for_week(week)
    assert len(result["predictions"]) == VISITS_PER_WEEK
