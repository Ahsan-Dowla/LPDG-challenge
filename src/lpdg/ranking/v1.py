"""Optimization V1 Gateway Ranking Strategy (FROZEN Part 1 Strategy).

Strategy: Technical Severity + Persistence + Corroboration + Business Exposure.
All formulas and weights are strictly frozen to preserve Part 1 integrity.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
import pandas as pd

from src.lpdg.config import (
    BASELINE_DAYS,
    EXPECTED_WEEKLY_HOURS,
    OPT_W_CORROBORATION,
    OPT_W_DISC,
    OPT_W_EXPOSURE,
    OPT_W_OFFLINE,
    OPT_W_PERSISTENCE,
    RECENT_DAYS,
    SCORED_WEEKS,
    STRATEGY_OPTIMIZED,
    STRATEGY_V1,
    VISITS_PER_WEEK,
)
from src.lpdg.data.loaders import active_gateways, normalize_gateway_id
from src.lpdg.exceptions import GatewayNotFoundError, PipelineExecutionError
from src.lpdg.features.telemetry import calc_raw_persistence, norm_by_max
from src.lpdg.ranking.interfaces import RankingStrategy


class V1Ranker(RankingStrategy):
    """Frozen Optimization V1 ranking strategy."""

    @property
    def name(self) -> str:
        return STRATEGY_OPTIMIZED

    def rank_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
    ) -> pd.DataFrame:
        """Rank eligible gateways for a single Monday cutoff using Optimization V1."""
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
                    columns=["gateway_id", "score", "coverage_hours", "problem_hours", "worst_signal"]
                )

            # Hourly problem flags
            has_offline = recent["offline_duration_sec"] > 0
            has_disc = recent["disconnection_cnt"] > 0
            has_problem = has_offline | has_disc

            recent_agg = recent.groupby("gateway_id").agg(
                tot_offline=("offline_duration_sec", "sum"),
                tot_disc=("disconnection_cnt", "sum"),
                tot_no_conn=("no_conn_importance", "sum"),
                coverage_hours=("ts", "count"),
            )
            problem_hours = has_problem.groupby(recent["gateway_id"]).sum()
            recent_agg["problem_hours"] = problem_hours

            # Technical severity
            tech_offline = norm_by_max(np.log1p(recent_agg["tot_offline"]))
            tech_disc = norm_by_max(np.log1p(recent_agg["tot_disc"]))
            technical = OPT_W_OFFLINE * tech_offline + OPT_W_DISC * tech_disc

            # Persistence (coverage-aware)
            persistence = calc_raw_persistence(
                recent_agg["problem_hours"],
                recent_agg["coverage_hours"],
                expected_hours=EXPECTED_WEEKLY_HOURS,
            )

            # Corroboration
            corroboration = norm_by_max(np.log1p(recent_agg["tot_no_conn"]))

            # Business exposure
            meter_map = master.set_index("gateway_id")["n_meters_installed"].to_dict()
            max_meters = master["n_meters_installed"].max()
            meters = recent_agg.index.map(meter_map)
            meters = pd.to_numeric(meters, errors="coerce").fillna(
                master["n_meters_installed"].mean()
            )
            exposure = np.log1p(meters) / np.log1p(max_meters)

            # Combine
            evidence = technical + OPT_W_PERSISTENCE * persistence + OPT_W_CORROBORATION * corroboration
            score = evidence * (1.0 + OPT_W_EXPOSURE * exposure)

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
            score_val = round(float(row.score), 4)
            reason = (
                f"Optimized V1: {prob_hrs}/{cov}h observed impaired ({signal}), "
                f"{silent_hrs}h silent of {EXPECTED_WEEKLY_HOURS}h expected; "
                f"{n_m} meters exposed; score={score_val}."
            )
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

        reason = (
            f"Optimized V1: {prob_hrs}/{cov}h observed impaired ({signal}), "
            f"{silent_hrs}h silent of {EXPECTED_WEEKLY_HOURS}h expected; "
            f"{n_m} meters exposed; score={score_val}."
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
            },
        }
