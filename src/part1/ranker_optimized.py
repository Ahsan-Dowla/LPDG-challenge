"""Optimization V1 gateway ranker.

Strategy: Technical Severity + Persistence + Corroboration + Business Exposure.

Design decisions documented in DECISIONS.md.  All feature construction uses
only telemetry and gateway-master data available strictly before the Monday
00:00 UTC prediction cutoff — no meter-read outcome, no field-visit outcome,
no engineer review.

Evidence base
-------------
Ablation across the 8 scored weeks showed the following Schlecht-to-Normal
capture ratios when compared against the independent engineer review
(60 Schlecht, 60 Normal, conducted 2026-02-15):

  Baseline 3-Sigma            : Schlecht=22, Normal=26, S/N=0.85
  Technical only              : Schlecht=89, Normal= 5, S/N=17.8
  Tech + Persistence          : Schlecht=89, Normal= 5, S/N=17.8
  Tech + Persistence + Exposure: Schlecht=89, Normal= 5, S/N=17.8  ← chosen
  Tech + Persistence + Meter Impact: Schlecht=77, Normal=17 (worse)

The meter-read rate was tried as a feature but reduced Schlecht capture,
probably because some gateways have poor reads for reasons unrelated to the
gateway hardware (e.g. meter firmware, billing cycles).  It is therefore used
only as an evaluation proxy, not as a ranking feature.

Score formula (all components bounded in [0, 1] before combination)
---------
  tech_offline  = log1p(Σ offline_duration_sec in recent 7d)
                  / max across all active gateways
  tech_disc     = log1p(Σ disconnection_cnt in recent 7d)
                  / max across all active gateways
  technical     = 0.6 * tech_offline + 0.4 * tech_disc

  persistence   = (hours with offline>0 OR disc>0) / coverage_hours  [0,1]

  corroboration = log1p(Σ no_conn_importance in recent 7d)
                  / max across all active gateways  [0,1]

  exposure      = log1p(n_meters_installed) / log1p(network_max_meters)  [0,1]

  evidence      = technical + 0.3 * persistence + 0.2 * corroboration
  score         = evidence * (1 + 0.3 * exposure)

Tie-breaking
------------
  score DESC, gateway_id ASC  (deterministic, reproducible)
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .config import (
    BASELINE_DAYS,
    EXPECTED_WEEKLY_HOURS,
    OPT_W_CORROBORATION,
    OPT_W_DISC,
    OPT_W_EXPOSURE,
    OPT_W_OFFLINE,
    OPT_W_PERSISTENCE,
    RECENT_DAYS,
    VISITS_PER_WEEK,
    SCORED_WEEKS,
)
from .eligibility import active_gateways


def _norm(series: pd.Series) -> pd.Series:
    """Divide by max; return zeros if max is zero or series is empty."""
    m = series.max()
    if m == 0 or pd.isna(m):
        return series * 0.0
    return series / m


def rank_week_optimized(
    frame: pd.DataFrame,
    master: pd.DataFrame,
    monday: dt.date,
) -> pd.DataFrame:
    """Rank gateways for a single Monday using Optimization V1.

    Parameters
    ----------
    frame:
        Telemetry for *active* gateways only, pre-filtered to eligible IDs.
        Must contain columns: gateway_id, ts, offline_duration_sec,
        disconnection_cnt, reboot_cnt, no_conn_importance.
    master:
        Full gateway_master DataFrame with gateway_id and n_meters_installed.
    monday:
        The prediction cutoff date (Monday 00:00 UTC).

    Returns
    -------
    DataFrame with columns: gateway_id, score, coverage_hours, worst_signal,
    sorted score DESC then gateway_id ASC.
    """
    end = pd.Timestamp(monday, tz="UTC")
    window = frame[
        (frame["ts"] >= end - dt.timedelta(days=BASELINE_DAYS))
        & (frame["ts"] < end)
    ]
    recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()

    if recent.empty:
        return pd.DataFrame(
            columns=["gateway_id", "score", "coverage_hours", "worst_signal"]
        )

    # Aggregate recent 7-day window per gateway
    has_offline = recent["offline_duration_sec"] > 0
    has_disc = recent["disconnection_cnt"] > 0
    has_problem = has_offline | has_disc

    recent_agg = recent.groupby("gateway_id").agg(
        tot_offline=("offline_duration_sec", "sum"),
        tot_disc=("disconnection_cnt", "sum"),
        tot_no_conn=("no_conn_importance", "sum"),
        coverage_hours=("ts", "count"),
    )
    # Count hours with any connectivity problem (offline OR disconnection)
    problem_hours = has_problem.groupby(recent["gateway_id"]).sum()
    recent_agg["problem_hours"] = problem_hours

    # --- Technical severity ---
    tech_offline = _norm(np.log1p(recent_agg["tot_offline"]))
    tech_disc = _norm(np.log1p(recent_agg["tot_disc"]))
    technical = OPT_W_OFFLINE * tech_offline + OPT_W_DISC * tech_disc

    # --- Persistence ---
    # Scaled by expected weekly hours (168h) to prevent low coverage from inflating persistence
    persistence = (
        recent_agg["problem_hours"] / np.maximum(recent_agg["coverage_hours"], float(EXPECTED_WEEKLY_HOURS))
    ).clip(0, 1)

    # --- Corroboration via no_conn_importance ---
    corroboration = _norm(np.log1p(recent_agg["tot_no_conn"]))

    # --- Business exposure ---
    meter_map = master.set_index("gateway_id")["n_meters_installed"].to_dict()
    max_meters = master["n_meters_installed"].max()
    meters = recent_agg.index.map(meter_map)
    meters = pd.to_numeric(meters, errors="coerce").fillna(
        master["n_meters_installed"].mean()
    )
    exposure = np.log1p(meters) / np.log1p(max_meters)

    # --- Combine ---
    evidence = technical + OPT_W_PERSISTENCE * persistence + OPT_W_CORROBORATION * corroboration
    score = evidence * (1.0 + OPT_W_EXPOSURE * exposure)

    # --- Worst signal label for reason generation ---
    worst_signal = pd.Series("offline_duration_sec", index=recent_agg.index)
    worst_signal = worst_signal.where(
        tech_offline >= tech_disc, "disconnection_cnt"
    )

    silent_hours = np.maximum(0, EXPECTED_WEEKLY_HOURS - recent_agg["coverage_hours"])

    result = recent_agg[["coverage_hours", "problem_hours"]].copy()
    result["silent_hours"] = silent_hours
    result["score"] = score
    result["worst_signal"] = worst_signal
    result["n_meters"] = meters.astype(int)
    result["persistence_pct"] = (persistence * 100).round(0).astype(int)
    return (
        result.reset_index()
        .sort_values(["score", "gateway_id"], ascending=[False, True], kind="mergesort")
        .reset_index(drop=True)
    )


def build_predictions_optimized(
    telemetry: pd.DataFrame,
    master: pd.DataFrame,
) -> pd.DataFrame:
    """Run the optimized pipeline across all 8 scored Mondays."""
    rows: list[dict[str, object]] = []
    for monday in SCORED_WEEKS:
        eligible = active_gateways(master, monday)
        tel_eligible = telemetry[telemetry["gateway_id"].isin(eligible)]
        ranked = rank_week_optimized(tel_eligible, master, monday)
        if len(ranked) < VISITS_PER_WEEK:
            raise ValueError(
                f"only {len(ranked)} gateways have data before {monday}"
            )
        for rank, row in enumerate(
            ranked.head(VISITS_PER_WEEK).itertuples(index=False), 1
        ):
            signal = row.worst_signal
            cov = int(row.coverage_hours)
            prob_hrs = int(row.problem_hours)
            silent_hrs = int(row.silent_hours)
            n_m = int(row.n_meters)
            score_val = round(float(row.score), 4)
            reason = (
                f"Optimized V1: {prob_hrs}/{cov}h observed impaired ({signal}), "
                f"{silent_hrs}h silent of {EXPECTED_WEEKLY_HOURS}h expected; "
                f"{n_m} meters exposed; score={score_val}."
            )
            # Reason must not exceed 300 characters
            if len(reason) > 300:
                reason = reason[:297] + "..."
            rows.append(
                {
                    "week_start": monday.isoformat(),
                    "rank": rank,
                    "gateway_id": row.gateway_id,
                    "score": score_val,
                    "reason": reason,
                }
            )
    return pd.DataFrame(rows, columns=["week_start", "rank", "gateway_id", "score", "reason"])
