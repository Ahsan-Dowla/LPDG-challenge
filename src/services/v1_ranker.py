"""V1 Optimized Ranker adapter implementing BaseRanker."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd

from src.part1.config import (
    EXPECTED_WEEKLY_HOURS,
    SCORED_WEEKS,
    STRATEGY_OPTIMIZED,
    VISITS_PER_WEEK,
)
from src.part1.data_loader import normalize_gateway_id
from src.part1.eligibility import active_gateways
from src.part1.ranker_optimized import build_predictions_optimized, rank_week_optimized

from .exceptions import GatewayNotFoundError, PipelineExecutionError
from .interfaces import BaseRanker


class V1OptimizedRanker(BaseRanker):
    """Production adapter wrapping the Part 1 frozen Optimization V1 ranker."""

    @property
    def name(self) -> str:
        return STRATEGY_OPTIMIZED

    def rank_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
    ) -> pd.DataFrame:
        """Rank active gateways for Monday cutoff using Optimization V1."""
        try:
            eligible = active_gateways(master, monday)
            tel_eligible = telemetry[telemetry["gateway_id"].isin(eligible)]
            return rank_week_optimized(tel_eligible, master, monday)
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
        """Run complete predictions across requested or default scored weeks."""
        target_weeks = weeks or SCORED_WEEKS
        # If target_weeks is exactly SCORED_WEEKS, we can call build_predictions_optimized directly
        if target_weeks == SCORED_WEEKS:
            try:
                return build_predictions_optimized(telemetry, master)
            except Exception as exc:
                raise PipelineExecutionError(f"Failed to build predictions: {exc}") from exc

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
        # Check rank in top 15 vs overall pool
        matches_indices = ranked.index[ranked["gateway_id"] == canonical_id].tolist()
        pos_in_pool = matches_indices[0] + 1
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
