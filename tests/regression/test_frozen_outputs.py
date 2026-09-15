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
    if not (DATA_DIR / "gateway_master.csv").exists():
        pytest.skip("Challenge data directory not present (requires private dataset)")
    return RankingService(data_dir=DATA_DIR, strategy=V1Ranker()).predict_all()


@pytest.fixture(scope="module")
def v2_predictions():
    if not (DATA_DIR / "gateway_master.csv").exists():
        pytest.skip("Challenge data directory not present (requires private dataset)")
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
    # Hash a canonical CRLF representation so the guard is stable across platforms.
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return hashlib.sha256(content).hexdigest().upper()


# ---------------------------------------------------------------------------
# Hash guards -- first line of defense
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Shape guards
# ---------------------------------------------------------------------------


@pytest.mark.challenge_data
def test_v1_shape(v1_predictions):
    assert len(v1_predictions) == VISITS_PER_WEEK * len(SCORED_WEEKS)
    assert v1_predictions["week_start"].nunique() == len(SCORED_WEEKS)


@pytest.mark.challenge_data
def test_v2_shape(v2_predictions):
    assert len(v2_predictions) == VISITS_PER_WEEK * len(SCORED_WEEKS)
    assert v2_predictions["week_start"].nunique() == len(SCORED_WEEKS)


# ---------------------------------------------------------------------------
# Rank completeness guards (1-15 each week)
# ---------------------------------------------------------------------------


@pytest.mark.challenge_data
@pytest.mark.parametrize("week", SCORED_WEEKS)
def test_v1_ranks_complete(v1_predictions, week):
    wdf = v1_predictions[v1_predictions["week_start"] == week.isoformat()]
    assert sorted(wdf["rank"].tolist()) == list(range(1, VISITS_PER_WEEK + 1))


@pytest.mark.challenge_data
@pytest.mark.parametrize("week", SCORED_WEEKS)
def test_v2_ranks_complete(v2_predictions, week):
    wdf = v2_predictions[v2_predictions["week_start"] == week.isoformat()]
    assert sorted(wdf["rank"].tolist()) == list(range(1, VISITS_PER_WEEK + 1))


# ---------------------------------------------------------------------------
# Full semantic comparison -- all 5 output columns: week_start, rank,
# gateway_id, score, reason.
# If someone accidentally changes the ranking algorithm, reason template,
# or score formula, this test catches it with a readable failure message.
# ---------------------------------------------------------------------------


@pytest.mark.challenge_data
def test_v1_live_matches_frozen(v1_predictions, v1_frozen):
    """Live V1 output must exactly match frozen reference across all 5 output columns."""
    live = v1_predictions.sort_values(["week_start", "rank"]).reset_index(drop=True)
    frozen = v1_frozen.sort_values(["week_start", "rank"]).reset_index(drop=True)

    # week_start must match exactly
    pd.testing.assert_series_equal(
        live["week_start"], frozen["week_start"], check_names=False, obj="V1 week_start"
    )
    # rank must match exactly
    pd.testing.assert_series_equal(
        live["rank"].astype(int), frozen["rank"].astype(int),
        check_names=False, obj="V1 rank"
    )
    # gateway_id -- exact per (week, rank)
    for _, row in frozen.iterrows():
        week, rank = row["week_start"], row["rank"]
        gws = live[(live["week_start"] == week) & (live["rank"] == rank)]["gateway_id"].values
        assert len(gws) == 1
        assert gws[0] == row["gateway_id"], (
            f"V1 gateway_id mismatch week={week} rank={rank}: "
            f"live={gws[0]} frozen={row['gateway_id']}"
        )
    # score -- rounded to 4 dp (matches V1 output format: round(float, 4))
    score_mismatches = (live["score"].round(4).values != frozen["score"].round(4).values).sum()
    assert score_mismatches == 0, f"V1: {score_mismatches} score mismatches"
    # reason -- exact string match (template change would flip this)
    reason_mismatches = (live["reason"].values != frozen["reason"].values).sum()
    assert reason_mismatches == 0, (
        f"V1: {reason_mismatches} reason string mismatches. "
        "Check that the reason template in V1Ranker.predict_week() is unchanged."
    )


@pytest.mark.challenge_data
def test_v2_live_matches_frozen(v2_predictions, v2_frozen):
    """Live V2 output must exactly match frozen reference across all 5 output columns."""
    live = v2_predictions.sort_values(["week_start", "rank"]).reset_index(drop=True)
    frozen = v2_frozen.sort_values(["week_start", "rank"]).reset_index(drop=True)

    # week_start must match exactly
    pd.testing.assert_series_equal(
        live["week_start"], frozen["week_start"], check_names=False, obj="V2 week_start"
    )
    # gateway_id -- exact per (week, rank)
    for _, row in frozen.iterrows():
        week, rank = row["week_start"], row["rank"]
        gws = live[(live["week_start"] == week) & (live["rank"] == rank)]["gateway_id"].values
        assert len(gws) == 1
        assert gws[0] == row["gateway_id"], (
            f"V2 gateway_id mismatch week={week} rank={rank}"
        )
    # score -- rounded to 2 dp (V2 scores are monetary estimates)
    score_mismatches = (live["score"].round(2).values != frozen["score"].round(2).values).sum()
    assert score_mismatches == 0, f"V2: {score_mismatches} score mismatches"
    # reason -- exact string match
    reason_mismatches = (live["reason"].values != frozen["reason"].values).sum()
    assert reason_mismatches == 0, f"V2: {reason_mismatches} reason string mismatches."


# ---------------------------------------------------------------------------
# No-future-leakage guards.
# A ranker that accidentally reads post-cutoff telemetry would produce
# different results on the truncated dataset. This detects that.
# ---------------------------------------------------------------------------


@pytest.mark.challenge_data
@pytest.mark.parametrize("week", SCORED_WEEKS)
def test_v1_no_future_leakage(week):
    """V1 predictions must be identical with full vs strictly pre-cutoff telemetry."""
    from src.lpdg.data.loaders import load_gateway_master, load_telemetry_extended

    telemetry = load_telemetry_extended(DATA_DIR)
    master = load_gateway_master(DATA_DIR)
    cutoff = pd.Timestamp(week, tz="UTC")

    ranker = V1Ranker()
    preds_full = ranker.predict_week(telemetry, master, week, limit=VISITS_PER_WEEK)

    # Truncate telemetry to strictly before the Monday cutoff
    telemetry_pre = telemetry[telemetry["ts"] < cutoff].copy()
    preds_pre = ranker.predict_week(telemetry_pre, master, week, limit=VISITS_PER_WEEK)

    pd.testing.assert_frame_equal(
        preds_full.reset_index(drop=True),
        preds_pre.reset_index(drop=True),
        obj=f"V1 leakage check week={week}",
    )