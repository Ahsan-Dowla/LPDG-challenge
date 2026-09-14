"""Gateway Ranking V2 — Probabilistic & Expected-Value Decision Ranker.

Decision Formulation:
---------------------
Given information available strictly up to each Monday 00:00 UTC, rank exactly
15 gateways that maximize the expected operational value of a physical site visit:

    E[Value of Visit to Gateway g] =
        P(gateway is impaired | evidence) * avoided_failure_cost(exposure)
        - (1 - P(gateway is impaired | evidence)) * wasted_visit_cost

Where:
  - wasted_visit_cost = €380 (dispatching a technician to a healthy gateway)
  - avoided_failure_cost = €600 * (1 + 0.3 * exposure) (avoided recurring loss)
  - exposure = log1p(n_meters_installed) / log1p(network_max_meters) in [0, 1]

Probabilistic Components:
-------------------------
1. Robust Anomaly Signal:
   Telemetry counters have severe non-Gaussian heavy tails and extreme spikes.
   Gaussian mean/std breaks down. We compute median absolute deviation (MAD)
   normalized robust z-scores on recent 7-day totals:
       z = (x - median(x)) / (1.4826 * MAD(x) + epsilon)
   Only positive deviations represent anomalies:
       z_pos = max(0, z)
   Normalized by active network maximum: S_metric = z_pos / max(z_pos).

2. Bayesian Beta-Binomial Persistence Probability:
   We model hourly impairment rate with a Beta prior:
       p_g ~ Beta(alpha_0, beta_0) with alpha_0=1.0, beta_0=9.0 (prior mean 0.10)
   Posterior mean with effective weekly sample size (168h):
       p_persistence = (alpha_0 + k_imp) / (alpha_0 + beta_0 + max(n_obs, 168))
   This naturally penalizes gateways with few observed hours (low coverage),
   shrinking their persistence toward the healthy prior.

3. Coverage / Silence Awareness:
   Explicitly separates observed impaired hours from silent hours:
       silent_hours = max(0, 168 - n_obs)
   Gateways with partial silence are penalized through posterior shrinkage.

4. Calibrated Probability of Impairment:
       evidence = technical + 0.30 * p_persistence + 0.15 * corroboration
       P(impaired) = clip(evidence / max(evidence), 0.01, 0.99)

5. Expected Value Decision Score (€):
       score = P(impaired) * avoided_cost - (1 - P(impaired)) * wasted_cost

Tie-breaking:
------------
  score DESC, gateway_id ASC  (deterministic, bit-for-bit reproducible)
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
import pandas as pd

from .config import (
    BASELINE_DAYS,
    EXPECTED_WEEKLY_HOURS,
    RECENT_DAYS,
    SCORED_WEEKS,
    V2_COST_UNATTENDED_FAILURE,
    V2_COST_WASTED_VISIT,
    V2_PRIOR_ALPHA,
    V2_PRIOR_BETA,
    V2_W_CONN,
    V2_W_CORROBORATION,
    V2_W_DISC,
    V2_W_EXPOSURE,
    V2_W_OFFLINE,
    V2_W_PERSISTENCE,
    VISITS_PER_WEEK,
)
from .eligibility import active_gateways


def robust_z_pos(series: pd.Series, eps: float = 1.0) -> pd.Series:
    """Compute robust positive z-scores using Median and MAD.

    Normalized to [0, 1] relative to the maximum observed positive deviation.
    """
    med = series.median()
    mad = np.median(np.abs(series - med))
    scale = 1.4826 * mad
    if scale == 0 or np.isnan(scale):
        raw_z = (series - med) / eps
    else:
        raw_z = (series - med) / scale

    # Only positive deviations represent degradation
    pos_z = np.maximum(0.0, raw_z)
    max_z = pos_z.max()
    if max_z > 0 and not np.isnan(max_z):
        return pos_z / max_z
    return pos_z * 0.0


def rank_week_v2(
    frame: pd.DataFrame,
    master: pd.DataFrame,
    monday: dt.date,
) -> pd.DataFrame:
    """Rank eligible gateways for a single Monday cutoff using V2 Expected Value.

    Parameters
    ----------
    frame:
        Telemetry for active gateways only, pre-filtered to eligible IDs.
        Columns: gateway_id, ts, offline_duration_sec, disconnection_cnt,
        reboot_cnt, no_conn_importance.
    master:
        Full gateway_master DataFrame with gateway_id and n_meters_installed.
    monday:
        The prediction cutoff date (Monday 00:00 UTC).

    Returns
    -------
    DataFrame with columns: gateway_id, score, p_impaired, ev_euro,
    coverage_hours, silent_hours, problem_hours, n_meters, worst_signal,
    sorted by score DESC then gateway_id ASC.
    """
    end = pd.Timestamp(monday, tz="UTC")
    window = frame[
        (frame["ts"] >= end - dt.timedelta(days=BASELINE_DAYS))
        & (frame["ts"] < end)
    ]
    recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()

    if recent.empty:
        return pd.DataFrame(
            columns=[
                "gateway_id",
                "score",
                "p_impaired",
                "ev_euro",
                "coverage_hours",
                "silent_hours",
                "problem_hours",
                "n_meters",
                "worst_signal",
            ]
        )

    # Hourly impairment indicator
    has_offline = recent["offline_duration_sec"] > 0
    has_disc = recent["disconnection_cnt"] > 0
    recent["impaired_hour"] = has_offline | has_disc

    agg = recent.groupby("gateway_id").agg(
        n_obs=("ts", "count"),
        k_imp=("impaired_hour", "sum"),
        tot_offline=("offline_duration_sec", "sum"),
        tot_disc=("disconnection_cnt", "sum"),
        tot_no_conn=("no_conn_importance", "sum"),
        tot_reboot=("reboot_cnt", "sum"),
    )

    # 1. Robust Anomaly Scores on log-transformed volumes
    rz_off = robust_z_pos(np.log1p(agg["tot_offline"]))
    rz_disc = robust_z_pos(np.log1p(agg["tot_disc"]))
    rz_conn = robust_z_pos(np.log1p(agg["tot_no_conn"]))
    rz_reb = robust_z_pos(np.log1p(agg["tot_reboot"]))

    technical = (
        V2_W_OFFLINE * rz_off
        + V2_W_DISC * rz_disc
        + V2_W_CONN * rz_conn
    )

    # 2. Bayesian Beta-Binomial Persistence Posterior Mean
    # Effective sample size incorporates expected weekly hours to prevent low coverage bias
    effective_n = np.maximum(agg["n_obs"], float(EXPECTED_WEEKLY_HOURS))
    p_persistence = (V2_PRIOR_ALPHA + agg["k_imp"]) / (
        V2_PRIOR_ALPHA + V2_PRIOR_BETA + effective_n
    )

    # 3. Coverage / Silence metrics
    silent_hours = np.maximum(0, EXPECTED_WEEKLY_HOURS - agg["n_obs"])

    # 4. Calibrated Probability of Impairment P(impaired | evidence)
    evidence = (
        technical
        + V2_W_PERSISTENCE * p_persistence
        + V2_W_CORROBORATION * rz_conn
    )
    max_ev = evidence.max()
    if max_ev > 0 and not np.isnan(max_ev):
        p_impaired = (evidence / max_ev).clip(0.01, 0.99)
    else:
        p_impaired = pd.Series(0.01, index=agg.index)

    # 5. Customer Exposure
    meter_map = master.set_index("gateway_id")["n_meters_installed"].to_dict()
    max_meters = master["n_meters_installed"].max()
    meters = agg.index.map(meter_map)
    meters = pd.to_numeric(meters, errors="coerce").fillna(
        master["n_meters_installed"].mean()
    )
    exposure = np.log1p(meters) / np.log1p(max_meters)

    # 6. Expected Value Decision Score (€)
    avoided_cost = V2_COST_UNATTENDED_FAILURE * (1.0 + V2_W_EXPOSURE * exposure)
    wasted_cost = V2_COST_WASTED_VISIT
    ev_euro = p_impaired * avoided_cost - (1.0 - p_impaired) * wasted_cost

    worst_signal = pd.Series("offline_duration_sec", index=agg.index)
    worst_signal = worst_signal.where(rz_off >= rz_disc, "disconnection_cnt")

    res = pd.DataFrame(
        {
            "gateway_id": agg.index,
            "score": ev_euro.values,
            "p_impaired": p_impaired.values,
            "ev_euro": ev_euro.values,
            "coverage_hours": agg["n_obs"].values,
            "silent_hours": silent_hours.values,
            "problem_hours": agg["k_imp"].values,
            "n_meters": meters.astype(int).values,
            "worst_signal": worst_signal.values,
            "persistence_pct": (p_persistence * 100).round(0).astype(int).values,
        }
    )

    return (
        res.sort_values(["score", "gateway_id"], ascending=[False, True], kind="mergesort")
        .reset_index(drop=True)
    )


def build_predictions_v2(
    telemetry: pd.DataFrame,
    master: pd.DataFrame,
    weeks: list[dt.date] | None = None,
) -> pd.DataFrame:
    """Run V2 Probabilistic Ranking pipeline across requested or default scored weeks."""
    target_weeks = weeks or SCORED_WEEKS
    rows: list[dict[str, Any]] = []

    for monday in target_weeks:
        eligible = active_gateways(master, monday)
        tel_eligible = telemetry[telemetry["gateway_id"].isin(eligible)]
        ranked = rank_week_v2(tel_eligible, master, monday)

        if len(ranked) < VISITS_PER_WEEK:
            raise ValueError(
                f"only {len(ranked)} gateways have data before {monday}, expected at least {VISITS_PER_WEEK}"
            )

        for rank, row in enumerate(
            ranked.head(VISITS_PER_WEEK).itertuples(index=False), 1
        ):
            signal = row.worst_signal
            cov = int(row.coverage_hours)
            prob_hrs = int(row.problem_hours)
            silent_hrs = int(row.silent_hours)
            n_m = int(row.n_meters)
            p_imp_pct = round(float(row.p_impaired) * 100, 1)
            ev_val = round(float(row.score), 2)
            score_formatted = round(float(row.score), 4)

            reason = (
                f"V2 Probabilistic: P(imp)={p_imp_pct}%, EV=+€{ev_val:.1f}; "
                f"{prob_hrs}/{cov}h impaired ({signal}), {silent_hrs}h silent; "
                f"{n_m} meters exposed."
            )
            if len(reason) > 300:
                reason = reason[:297] + "..."

            rows.append(
                {
                    "week_start": monday.isoformat(),
                    "rank": rank,
                    "gateway_id": row.gateway_id,
                    "score": score_formatted,
                    "reason": reason,
                }
            )

    return pd.DataFrame(
        rows, columns=["week_start", "rank", "gateway_id", "score", "reason"]
    )
