from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .config import (
    BASELINE_DAYS,
    METRICS,
    RECENT_DAYS,
    SCORED_WEEKS,
    SIGMA,
    VISITS_PER_WEEK,
)
from .eligibility import active_gateways


def rank_week(frame: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
    """Rank gateways using the supplied gateway-specific 3-sigma baseline."""
    end = pd.Timestamp(monday, tz="UTC")
    window = frame[
        (frame["ts"] >= end - dt.timedelta(days=BASELINE_DAYS))
        & (frame["ts"] < end)
    ]
    if window.empty:
        return pd.DataFrame(columns=["gateway_id", "flagged_hours", "worst_metric", "coverage_hours"])

    stats = window.groupby("gateway_id")[METRICS].agg(["mean", "std"])
    recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()

    flags = pd.Series(0, index=recent.index, dtype=int)
    worst = pd.Series("", index=recent.index, dtype=object)
    for metric in METRICS:
        mean = recent["gateway_id"].map(stats[(metric, "mean")])
        std = recent["gateway_id"].map(stats[(metric, "std")]).replace(0, np.nan)
        exceeded = ((recent[metric] - mean) > SIGMA * std).fillna(False)
        flags = flags + exceeded.astype(int)
        worst = worst.where(~exceeded | (worst != ""), metric)

    recent["flagged"] = flags
    recent["worst_metric"] = worst
    grouped = recent.groupby("gateway_id").agg(
        flagged_hours=("flagged", "sum"),
        worst_metric=("worst_metric", lambda values: next((value for value in values if value), "")),
        coverage_hours=("ts", "count"),
    )
    return (
        grouped.reset_index()
        .sort_values(["flagged_hours", "gateway_id"], ascending=[False, True], kind="mergesort")
        .reset_index(drop=True)
    )


def build_predictions(telemetry: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for monday in SCORED_WEEKS:
        eligible = telemetry[
            telemetry["gateway_id"].isin(active_gateways(master, monday))
        ]
        ranked = rank_week(eligible, monday)
        if len(ranked) < VISITS_PER_WEEK:
            raise ValueError(f"only {len(ranked)} gateways have data before {monday}")
        for rank, row in enumerate(ranked.head(VISITS_PER_WEEK).itertuples(index=False), 1):
            metric = row.worst_metric or "no metric over 3 sigma"
            coverage = int(row.coverage_hours)
            rows.append(
                {
                    "week_start": monday.isoformat(),
                    "rank": rank,
                    "gateway_id": row.gateway_id,
                    "score": float(row.flagged_hours),
                    "reason": (
                        f"{row.flagged_hours} anomalous metric-hour(s) in the last 7 days "
                        f"against this gateway's own 28-day baseline; strongest breach: {metric}. "
                        f"Observed {coverage}/168 recent hours."
                    ),
                }
            )
    return pd.DataFrame(rows, columns=["week_start", "rank", "gateway_id", "score", "reason"])
