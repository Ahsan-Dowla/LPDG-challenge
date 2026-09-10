"""Part 1 test suite.

Tests cover:
- ID normalisation
- Temporal cutoff (no future rows)
- Duplicate deduplication
- Decommissioning eligibility
- Tie determinism (baseline)
- Weekly shape (baseline)
- Optimized ranker: cutoff enforcement
- Optimized ranker: determinism
- Optimized ranker: no future data use
- Optimized ranker: missing no_conn_importance
- Optimized ranker: weekly shape
- Optimized ranker: score monotone with technical severity
- Pipeline: unknown strategy raises ValueError
- Pipeline: baseline strategy unchanged
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.part1 import data_loader
from src.part1.config import (
    OUTPUT_COLUMNS,
    STRATEGY_BASELINE,
    STRATEGY_OPTIMIZED,
    VISITS_PER_WEEK,
)
from src.part1.data_loader import normalize_gateway_id
from src.part1.eligibility import active_gateways
from src.part1.ranker import build_predictions, rank_week
from src.part1.ranker_optimized import build_predictions_optimized, rank_week_optimized


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def telemetry_rows(
    gateway_id: str,
    timestamps: list[str],
    value: float = 0.0,
    no_conn: float = 0.0,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gateway_id": gateway_id,
            "ts": pd.to_datetime(timestamps, utc=True),
            "offline_duration_sec": value,
            "disconnection_cnt": value,
            "reboot_cnt": value,
            "no_conn_importance": no_conn,
        }
    )


def make_master(gateway_ids: list[str], meters: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gateway_id": gateway_ids,
            "installed_on": [dt.date(2020, 1, 1)] * len(gateway_ids),
            "decommissioned_on": [None] * len(gateway_ids),
            "n_meters_installed": [meters] * len(gateway_ids),
        }
    )


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def test_gateway_ids_normalize_across_formats() -> None:
    assert normalize_gateway_id("02:02:cb:0a:6b:1f") == "0202CB0A6B1F"
    assert normalize_gateway_id(" 0202cb0a6b1f ") == "0202CB0A6B1F"


# ---------------------------------------------------------------------------
# Baseline ranker
# ---------------------------------------------------------------------------


def test_rank_week_uses_only_rows_before_monday() -> None:
    frame = pd.concat(
        [
            telemetry_rows("AAA", ["2026-01-31T23:00:00Z"]),
            telemetry_rows("AAA", ["2026-02-02T00:00:00Z"], value=999),
        ],
        ignore_index=True,
    )
    # Only baseline rank_week signature — pass basic 3-column frame
    frame_basic = frame[["gateway_id", "ts", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"]].copy()
    ranked = rank_week(frame_basic, dt.date(2026, 2, 2))
    assert ranked.iloc[0]["coverage_hours"] == 1
    assert ranked.iloc[0]["flagged_hours"] == 0


def test_duplicate_hour_is_removed_by_loader(monkeypatch, tmp_path) -> None:
    frame = telemetry_rows(
        "AAA",
        ["2026-01-26T00:00:00Z", "2026-01-27T00:00:00Z", "2026-01-28T00:00:00Z"],
        value=0,
    )
    duplicate = frame.iloc[[2]].copy()
    with_duplicate = pd.concat([frame, duplicate], ignore_index=True).rename(
        columns={"ts": "ts_utc"}
    )
    monkeypatch.setattr(data_loader.pd, "read_parquet", lambda *args, **kwargs: with_duplicate)
    loaded = data_loader.load_telemetry(tmp_path)
    assert len(loaded) == 3
    assert loaded["ts"].nunique() == 3


def test_decommissioned_gateway_is_ineligible_at_cutoff() -> None:
    master = pd.DataFrame(
        {
            "gateway_id": ["ACTIVE", "RETIRED", "FUTURE"],
            "installed_on": [dt.date(2020, 1, 1)] * 3,
            "decommissioned_on": [None, dt.date(2026, 2, 2), None],
        }
    )
    master.loc[2, "installed_on"] = dt.date(2026, 2, 3)
    assert active_gateways(master, dt.date(2026, 2, 2)) == {"ACTIVE"}


def test_ties_are_sorted_by_gateway_id() -> None:
    frame = pd.concat(
        [
            telemetry_rows("ZZZ", ["2026-01-31T23:00:00Z"]),
            telemetry_rows("AAA", ["2026-01-31T23:00:00Z"]),
        ],
        ignore_index=True,
    )
    frame = frame[["gateway_id", "ts", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"]].copy()
    ranked = rank_week(frame, dt.date(2026, 2, 2))
    assert ranked["gateway_id"].tolist() == ["AAA", "ZZZ"]


def test_build_predictions_has_required_weekly_shape() -> None:
    gateways = [f"{index:012X}" for index in range(15)]
    timestamps = pd.date_range("2026-01-01", "2026-03-23", freq="D", tz="UTC")
    rows = []
    for gateway_id in gateways:
        for timestamp in timestamps:
            rows.append(
                {
                    "gateway_id": gateway_id,
                    "ts": timestamp,
                    "offline_duration_sec": 0,
                    "disconnection_cnt": 0,
                    "reboot_cnt": 0,
                }
            )
    telemetry = pd.DataFrame(rows)
    master = pd.DataFrame(
        {
            "gateway_id": gateways,
            "installed_on": [dt.date(2020, 1, 1)] * 15,
            "decommissioned_on": [None] * 15,
        }
    )

    predictions = build_predictions(telemetry, master)

    assert predictions.columns.tolist() == OUTPUT_COLUMNS
    assert len(predictions) == 120
    assert predictions.groupby("week_start").size().tolist() == [15] * 8
    assert predictions.groupby("week_start")["rank"].apply(list).tolist() == [list(range(1, 16))] * 8


# ---------------------------------------------------------------------------
# Optimized ranker
# ---------------------------------------------------------------------------


def _build_optimized_telemetry(gateway_ids: list[str]) -> pd.DataFrame:
    """Synthetic full telemetry including no_conn_importance for 8-week window."""
    timestamps = pd.date_range("2026-01-01", "2026-03-23", freq="D", tz="UTC")
    rows = []
    for gateway_id in gateway_ids:
        for timestamp in timestamps:
            rows.append(
                {
                    "gateway_id": gateway_id,
                    "ts": timestamp,
                    "offline_duration_sec": 0.0,
                    "disconnection_cnt": 0.0,
                    "reboot_cnt": 0.0,
                    "no_conn_importance": 0.0,
                }
            )
    return pd.DataFrame(rows)


def test_optimized_rank_week_excludes_future_rows() -> None:
    """Rows at or after Monday must not influence the score."""
    frame = pd.concat(
        [
            telemetry_rows("AAA", ["2026-01-31T23:00:00Z"], value=1000.0, no_conn=1e6),
            telemetry_rows("AAA", ["2026-02-02T00:00:00Z"], value=0.0, no_conn=0.0),
            telemetry_rows("BBB", ["2026-01-31T23:00:00Z"], value=0.0, no_conn=0.0),
        ],
        ignore_index=True,
    )
    master = make_master(["AAA", "BBB"])
    ranked = rank_week_optimized(frame, master, dt.date(2026, 2, 2))
    # AAA should rank first (high offline in the valid window)
    assert ranked.iloc[0]["gateway_id"] == "AAA"
    # Coverage of AAA should be 1, not 2 (the future row is excluded)
    aaa = ranked[ranked["gateway_id"] == "AAA"]
    assert int(aaa["coverage_hours"].iloc[0]) == 1


def test_optimized_rank_week_deterministic() -> None:
    """Running twice must produce identical results."""
    gateways = [f"{i:012X}" for i in range(5)]
    frame = _build_optimized_telemetry(gateways)
    master = make_master(gateways)
    monday = dt.date(2026, 2, 9)
    result1 = rank_week_optimized(frame, master, monday)
    result2 = rank_week_optimized(frame, master, monday)
    pd.testing.assert_frame_equal(result1, result2)


def test_optimized_rank_week_tie_break_by_gateway_id() -> None:
    """Identical scores must break on gateway_id ascending."""
    frame = pd.concat(
        [
            telemetry_rows("ZZZ", ["2026-01-31T23:00:00Z"], value=1000.0, no_conn=1000.0),
            telemetry_rows("AAA", ["2026-01-31T23:00:00Z"], value=1000.0, no_conn=1000.0),
        ],
        ignore_index=True,
    )
    master = make_master(["AAA", "ZZZ"])
    ranked = rank_week_optimized(frame, master, dt.date(2026, 2, 2))
    assert ranked.iloc[0]["gateway_id"] == "AAA"


def test_optimized_rank_week_missing_no_conn_importance() -> None:
    """Ranker must not crash when no_conn_importance is all zeros."""
    gateways = [f"{i:012X}" for i in range(5)]
    frame = _build_optimized_telemetry(gateways)
    frame["no_conn_importance"] = 0.0  # explicitly all zeros
    master = make_master(gateways)
    ranked = rank_week_optimized(frame, master, dt.date(2026, 2, 9))
    assert len(ranked) == 5  # all gateways present, no crash


def test_optimized_score_higher_for_more_severe_gateway() -> None:
    """A gateway with much higher offline duration should score strictly higher."""
    severe = telemetry_rows(
        "SEVERE",
        ["2026-01-28T00:00:00Z", "2026-01-29T00:00:00Z"],
        value=3600.0,
        no_conn=10000.0,
    )
    mild = telemetry_rows(
        "MILD",
        ["2026-01-28T00:00:00Z", "2026-01-29T00:00:00Z"],
        value=0.0,
        no_conn=0.0,
    )
    frame = pd.concat([severe, mild], ignore_index=True)
    master = make_master(["SEVERE", "MILD"])
    ranked = rank_week_optimized(frame, master, dt.date(2026, 2, 2))
    scores = ranked.set_index("gateway_id")["score"]
    assert scores["SEVERE"] > scores["MILD"]


def test_optimized_build_predictions_weekly_shape() -> None:
    """Optimized pipeline must produce exactly 8 weeks × 15 rows = 120."""
    gateways = [f"{index:012X}" for index in range(15)]
    telemetry = _build_optimized_telemetry(gateways)
    master = make_master(gateways)

    predictions = build_predictions_optimized(telemetry, master)

    assert predictions.columns.tolist() == OUTPUT_COLUMNS
    assert len(predictions) == 120
    assert predictions.groupby("week_start").size().tolist() == [15] * 8
    assert predictions.groupby("week_start")["rank"].apply(list).tolist() == [list(range(1, 16))] * 8


def test_optimized_build_predictions_reasons_under_300_chars() -> None:
    """All reason fields must be non-empty and under 300 characters."""
    gateways = [f"{index:012X}" for index in range(15)]
    telemetry = _build_optimized_telemetry(gateways)
    master = make_master(gateways)
    predictions = build_predictions_optimized(telemetry, master)
    assert (predictions["reason"].str.len() <= 300).all()
    assert (predictions["reason"].str.len() > 0).all()


def test_optimized_build_predictions_scores_numeric() -> None:
    """Score must be numeric and non-null for all rows."""
    gateways = [f"{index:012X}" for index in range(15)]
    telemetry = _build_optimized_telemetry(gateways)
    master = make_master(gateways)
    predictions = build_predictions_optimized(telemetry, master)
    assert predictions["score"].notna().all()
    assert pd.api.types.is_numeric_dtype(predictions["score"])


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


def test_pipeline_unknown_strategy_raises() -> None:
    """Passing an unrecognised strategy must raise ValueError."""
    from src.part1.pipeline import run
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="unknown strategy"):
            run(pathlib.Path(tmp), pathlib.Path(tmp) / "out.csv", strategy="magic")
