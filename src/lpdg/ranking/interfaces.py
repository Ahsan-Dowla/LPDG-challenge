"""Protocol interface defining ranking strategies."""

from __future__ import annotations

import datetime as dt
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class RankingStrategy(Protocol):
    """Protocol defining the required interface for all gateway ranking strategies."""

    @property
    def name(self) -> str:
        """Unique strategy name identifier."""
        ...

    def rank_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
    ) -> pd.DataFrame:
        """Rank eligible gateways for a single Monday cutoff.

        Returns DataFrame sorted descending by score with at least `gateway_id` and `score`.
        """
        ...

    def predict_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
        limit: int = 15,
    ) -> pd.DataFrame:
        """Generate formatted top-N prediction rows for a single Monday cutoff.

        Returns DataFrame with columns: week_start, rank, gateway_id, score, reason.
        """
        ...

    def predict_all(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        weeks: list[dt.date] | None = None,
    ) -> pd.DataFrame:
        """Generate formatted predictions across requested or default scored weeks."""
        ...

    def explain_gateway(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
        gateway_id: str,
    ) -> dict[str, Any]:
        """Produce operational explanation and evidence metrics for a gateway."""
        ...
