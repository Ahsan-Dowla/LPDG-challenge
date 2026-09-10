"""Abstract interface for gateway rankers."""

from __future__ import annotations

import datetime as dt
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class BaseRanker(Protocol):
    """Protocol defining the interface for gateway ranking and prediction implementations."""

    @property
    def name(self) -> str:
        """Name of the ranking strategy."""
        ...

    def rank_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
    ) -> pd.DataFrame:
        """Rank eligible gateways for a single Monday cutoff.

        Returns a DataFrame sorted descending by score with columns including
        at least `gateway_id` and `score`.
        """
        ...

    def predict_week(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
        limit: int = 15,
    ) -> pd.DataFrame:
        """Generate top-N formatted prediction rows for a single Monday cutoff.

        Returns a DataFrame with columns:
        `week_start`, `rank`, `gateway_id`, `score`, `reason`.
        """
        ...

    def predict_all(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        weeks: list[dt.date] | None = None,
    ) -> pd.DataFrame:
        """Generate complete predictions across specified weeks.

        Returns a DataFrame with columns:
        `week_start`, `rank`, `gateway_id`, `score`, `reason`.
        """
        ...

    def explain_gateway(
        self,
        telemetry: pd.DataFrame,
        master: pd.DataFrame,
        monday: dt.date,
        gateway_id: str,
    ) -> dict[str, Any]:
        """Produce operational explanation and evidence metrics for a gateway at the cutoff.

        Returns a dictionary containing rank (if available), score, reason,
        and supporting telemetry/operational details.
        """
        ...
