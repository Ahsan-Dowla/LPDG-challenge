"""Probabilistic & Expected-Value V2 Gateway Ranking Strategy (Part 2 Strategy).

Decision Formulation:
---------------------
Given information available strictly up to each Monday 00:00 UTC, rank exactly
15 gateways that maximize the estimated operational value of a physical site visit:

    E[Value of Visit to Gateway g] =
        P(gateway is impaired | evidence) * avoided_failure_cost(exposure)
        - (1 - P(gateway is impaired | evidence)) * wasted_visit_cost

Where:
  - wasted_visit_cost = €380 (dispatching a technician to a healthy gateway)
  - avoided_failure_cost = €600 * (1 + 0.3 * exposure) (avoided recurring loss)
  - exposure = log1p(n_meters_installed) / log1p(network_max_meters) in [0, 1]
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
import pandas as pd

from src.lpdg.config import (
    BASELINE_DAYS,
    EXPECTED_WEEKLY_HOURS,
    RECENT_DAYS,
    SCORED_WEEKS,
    STRATEGY_V2,
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
from src.lpdg.data.loaders import active_gateways, normalize_gateway_id
from src.lpdg.exceptions import GatewayNotFoundError, PipelineExecutionError
from src.lpdg.features.telemetry import calc_bayesian_persistence, robust_z_pos
from src.lpdg.ranking.interfaces import RankingStrategy


class V2Ranker(RankingStrategy):
    """Probabilistic & Expected-Value V2 ranking strategy."""

    @property
    def name(self) -> str:
        return STRATEGY_V2

    def rank_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
    ) -> pd.DataFrame:
        """Rank eligible gateways for a single Monday cutoff using V2 Expected Value."""
        try:
            eligible = active_gateways(master, monday)
            frame = telemetry[telemetry["gateway_id"].isin(eligible)]

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

            # 1. Robust positive anomaly scores
            rz_off = robust_z_pos(np.log1p(agg["tot_offline"]))
            rz_disc = robust_z_pos(np.log1p(agg["tot_disc"]))
            rz_conn = robust_z_pos(np.log1p(agg["tot_no_conn"]))

            technical = (
                V2_W_OFFLINE * rz_off
                + V2_W_DISC * rz_disc
                + V2_W_CONN * rz_conn
            )

            # 2. Bayesian Beta-Binomial persistence with coverage shrinkage
            p_persistence = calc_bayesian_persistence(
                agg["k_imp"],
                agg["n_obs"],
                alpha=V2_PRIOR_ALPHA,
                beta=V2_PRIOR_BETA,
                expected_hours=EXPECTED_WEEKLY_HOURS,
            )

            # 3. Coverage / Silence metrics
            silent_hours = np.maximum(0, EXPECTED_WEEKLY_HOURS - agg["n_obs"])

            # 4. Estimated probability of impairment
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
        except Exception as exc:
            raise PipelineExecutionError(f"Failed to rank week {monday}: {exc}") from exc

    def predict_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
        limit: int = VISITS_PER_WEEK,
    ) -> pd.DataFrame:
        """Produce top-N prediction rows for Monday cutoff."""
        ranked = self.rank_week(telemetry, master, monday)
        if len(ranked) < limit:
            raise PipelineExecutionError(
                f"only {len(ranked)} gateways have data before {monday}, expected at least {limit}"
            )

        rows: list[dict[str, Any]] = []
        for rank, row in enumerate(ranked.head(limit).itertuples(index=False), 1):
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
        return pd.DataFrame(rows, columns=["week_start", "rank", "gateway_id", "score", "reason"])

    def predict_all(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        weeks: list[dt.date] | None = None,
    ) -> pd.DataFrame:
        """Generate predictions across requested or default scored weeks."""
        target_weeks = weeks or SCORED_WEEKS
        frames: list[pd.DataFrame] = []
        for w in target_weeks:
            frames.append(self.predict_week(telemetry, master, w, limit=VISITS_PER_WEEK))
        return pd.concat(frames, ignore_index=True)

    def explain_gateway(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
        gateway_id: str,
    ) -> dict[str, Any]:
        """Explain the ranking of a gateway for the given Monday cutoff."""
        canonical_id = normalize_gateway_id(gateway_id)
        ranked = self.rank_week(telemetry, master, monday)

        match = ranked[ranked["gateway_id"] == canonical_id]
        if match.empty:
            raise GatewayNotFoundError(
                f"Gateway '{gateway_id}' not found in evaluated active set for week {monday.isoformat()}"
            )

        row = match.iloc[0]
        pos_in_pool = ranked.index[ranked["gateway_id"] == canonical_id].tolist()[0] + 1
        rank_top15: int | None = pos_in_pool if pos_in_pool <= VISITS_PER_WEEK else None

        signal = row["worst_signal"]
        cov = int(row["coverage_hours"])
        prob_hrs = int(row["problem_hours"])
        silent_hrs = int(row["silent_hours"])
        n_m = int(row["n_meters"])
        score_val = round(float(row["score"]), 4)
        pers_pct = int(row["persistence_pct"])
        p_imp_pct = round(float(row["p_impaired"]) * 100, 1)
        ev_val = round(float(row["score"]), 2)

        reason = (
            f"V2 Probabilistic: P(imp)={p_imp_pct}%, EV=+€{ev_val:.1f}; "
            f"{prob_hrs}/{cov}h impaired ({signal}), {silent_hrs}h silent; "
            f"{n_m} meters exposed."
        )
        if len(reason) > 300:
            reason = reason[:297] + "..."

        return {
            "gateway_id": canonical_id,
            "week_start": monday.isoformat(),
            "rank": rank_top15,
            "overall_rank": pos_in_pool,
            "score": score_val,
            "reason": reason,
            "details": {
                "coverage_hours": cov,
                "problem_hours": prob_hrs,
                "silent_hours": silent_hrs,
                "expected_hours": EXPECTED_WEEKLY_HOURS,
                "worst_signal": signal,
                "n_meters_installed": n_m,
                "persistence_pct": pers_pct,
                "estimated_impairment_probability": round(float(row["p_impaired"]), 4),
                "estimated_expected_value_euro": ev_val,
                "probability_impaired": round(float(row["p_impaired"]), 4),
                "expected_value_euro": ev_val,
            },
        }
