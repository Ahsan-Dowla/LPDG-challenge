"""Baseline 3-Sigma Gateway Ranking Strategy."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd

from src.lpdg.config import (
    BASELINE_DAYS,
    METRICS,
    RECENT_DAYS,
    SCORED_WEEKS,
    SIGMA,
    STRATEGY_BASELINE,
    VISITS_PER_WEEK,
)
from src.lpdg.data.loaders import active_gateways, normalize_gateway_id
from src.lpdg.exceptions import GatewayNotFoundError, PipelineExecutionError
from src.lpdg.ranking.interfaces import RankingStrategy


class BaselineRanker(RankingStrategy):
    """Reference 3-Sigma anomaly-count ranking strategy."""

    @property
    def name(self) -> str:
        return STRATEGY_BASELINE

    def rank_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
    ) -> pd.DataFrame:
        """Rank eligible gateways for a single Monday cutoff using the 3-sigma algorithm."""
        try:
            eligible = active_gateways(master, monday)
            frame = telemetry[telemetry["gateway_id"].isin(eligible)]

            end = pd.Timestamp(monday, tz="UTC")
            window = frame[
                (frame["ts"] >= end - dt.timedelta(days=BASELINE_DAYS))
                & (frame["ts"] < end)
            ]
            recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)]

            if recent.empty:
                return pd.DataFrame(
                    columns=["gateway_id", "score"] + [f"{m}_flags" for m in METRICS]
                )

            # Compute baseline mean & std per gateway
            stats = window.groupby("gateway_id")[METRICS].agg(["mean", "std"])
            recent_joined = recent.join(stats, on="gateway_id")

            flags_by_metric: dict[str, pd.Series] = {}
            flag_cols: list[str] = []
            for m in METRICS:
                mean_col = (m, "mean")
                std_col = (m, "std")
                col_name = f"{m}_flags"
                flag_cols.append(col_name)

                threshold = recent_joined[mean_col] + SIGMA * recent_joined[std_col]
                is_anomaly = (recent_joined[std_col] > 0) & (
                    recent_joined[m] > threshold
                )
                flags_by_metric[col_name] = is_anomaly.groupby(
                    recent_joined["gateway_id"]
                ).sum()

            flags_df = pd.DataFrame(flags_by_metric)
            flags_df["score"] = flags_df[flag_cols].sum(axis=1)

            # Reindex across all active gateways with recent telemetry
            active_recent = set(recent["gateway_id"].unique())
            result = flags_df.reindex(sorted(active_recent), fill_value=0).reset_index()

            # Deterministic sorting: score DESC, gateway_id ASC
            result = result.sort_values(
                by=["score", "gateway_id"], ascending=[False, True], kind="mergesort"
            ).reset_index(drop=True)
            return result
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
            flag_parts = [f"{m}: {int(getattr(row, f'{m}_flags'))}" for m in METRICS]
            score_val = int(row.score)
            reason = (
                f"Baseline 3-sigma: {score_val} metric-hours >3sigma in past 7d "
                f"({', '.join(flag_parts)})."
            )
            if len(reason) > 300:
                reason = reason[:297] + "..."
            rows.append(
                {
                    "week_start": monday.isoformat(),
                    "rank": rank,
                    "gateway_id": row.gateway_id,
                    "score": float(score_val),
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

        flag_parts = [f"{m}: {int(row[f'{m}_flags'])}" for m in METRICS]
        score_val = int(row["score"])
        reason = (
            f"Baseline 3-sigma: {score_val} metric-hours >3sigma in past 7d "
            f"({', '.join(flag_parts)})."
        )
        if len(reason) > 300:
            reason = reason[:297] + "..."

        return {
            "gateway_id": canonical_id,
            "week_start": monday.isoformat(),
            "rank": rank_top15,
            "overall_rank": pos_in_pool,
            "score": float(score_val),
            "reason": reason,
            "details": {
                "metric_hours_flagged": score_val,
                "offline_duration_sec_flags": int(row["offline_duration_sec_flags"]),
                "disconnection_cnt_flags": int(row["disconnection_cnt_flags"]),
                "reboot_cnt_flags": int(row["reboot_cnt_flags"]),
            },
        }
