"""Regression test suite for Part 1 persistence & coverage bug."""

from __future__ import annotations

import datetime as dt
import pandas as pd
import pytest

from src.part1.config import EXPECTED_WEEKLY_HOURS
from src.part1.ranker_optimized import rank_week_optimized


def _make_telemetry_stream(gateway_id: str, hours: int, start_monday: dt.datetime) -> pd.DataFrame:
    """Generate hourly impaired telemetry for `hours` count prior to cutoff."""
    # Place rows in the 7-day recent window: (start_monday - 7 days) to start_monday
    base = start_monday - dt.timedelta(hours=hours)
    timestamps = [base + dt.timedelta(hours=i) for i in range(hours)]
    return pd.DataFrame(
        {
            "gateway_id": gateway_id,
            "ts": pd.to_datetime(timestamps, utc=True),
            "offline_duration_sec": 3600.0,  # fully offline
            "disconnection_cnt": 10.0,
            "reboot_cnt": 0.0,
            "no_conn_importance": 100.0,
        }
    )


def test_regression_small_coverage_does_not_inflate_persistence() -> None:
    """REGRESSION TEST: Protects against treating partial-coverage gateways as 100% persistent.

    Bug context:
    In early versions, persistence was computed as:
        problem_hours / coverage_hours
    For a gateway that reported only 20 hours in the week (and was offline/silent for 148h),
    20/20 gave persistence = 1.0 (100%), erroneously matching or beating a continuously
    failing gateway observed for all 168 hours.

    The fix enforces:
        persistence = problem_hours / max(coverage_hours, 168)
    This test asserts that 20 observed failing hours cannot achieve the same persistence
    or score as 168 observed failing hours.
    """
    cutoff = dt.date(2026, 2, 2)
    cutoff_dt = dt.datetime(2026, 2, 2, 0, 0, tzinfo=dt.timezone.utc)

    # Gateway A: 20 observed hours (all 20 impaired, 148 unobserved/silent)
    df_a = _make_telemetry_stream("GW_20H_OBSERVED", 20, cutoff_dt)

    # Gateway B: 168 observed hours (all 168 impaired, 0 silent)
    df_b = _make_telemetry_stream("GW_168H_OBSERVED", 168, cutoff_dt)

    telemetry = pd.concat([df_a, df_b], ignore_index=True)
    master = pd.DataFrame(
        {
            "gateway_id": ["GW_20H_OBSERVED", "GW_168H_OBSERVED"],
            "installed_on": [dt.date(2020, 1, 1)] * 2,
            "decommissioned_on": [None] * 2,
            "n_meters_installed": [100, 100],  # Equal exposure
        }
    )

    ranked = rank_week_optimized(telemetry, master, cutoff)
    indexed = ranked.set_index("gateway_id")

    row_a = indexed.loc["GW_20H_OBSERVED"]
    row_b = indexed.loc["GW_168H_OBSERVED"]

    # 1. GW_168H must strictly outrank and outscore GW_20H
    assert row_b["score"] > row_a["score"], (
        f"168h failing gateway score ({row_b['score']}) must be strictly higher than "
        f"20h failing gateway score ({row_a['score']})"
    )

    # 2. Persistence percentage of GW_20H must reflect 20 / 168 (~12%), NOT 20 / 20 (100%)
    expected_pers_pct_a = round((20.0 / EXPECTED_WEEKLY_HOURS) * 100)
    assert row_a["persistence_pct"] == expected_pers_pct_a, (
        f"GW_20H persistence_pct should be {expected_pers_pct_a}%, found {row_a['persistence_pct']}%"
    )
    assert row_b["persistence_pct"] == 100

    # 3. Silent hours must be accurately recorded
    assert row_a["silent_hours"] == 168 - 20
    assert row_b["silent_hours"] == 0
    assert row_a["coverage_hours"] == 20
    assert row_b["coverage_hours"] == 168
