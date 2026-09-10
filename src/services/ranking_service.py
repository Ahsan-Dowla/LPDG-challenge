"""Domain service coordinating data loading, ranking, and explanation."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import threading
from typing import Any

import pandas as pd

from src.part1.config import (
    DEFAULT_STRATEGY,
    SCORED_WEEKS,
    STRATEGY_OPTIMIZED,
)
from src.part1.data_loader import (
    load_gateway_master,
    load_telemetry,
    load_telemetry_extended,
)
from src.part1.output import write_predictions

from .exceptions import (
    DataNotFoundError,
    InvalidWeekError,
    PipelineExecutionError,
)
from .interfaces import BaseRanker
from .v1_ranker import V1OptimizedRanker


class RankingService:
    """Service layer encapsulating dataset management and ranking operations."""

    def __init__(
        self,
        data_dir: Path | str = "data",
        ranker: BaseRanker | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.ranker = ranker if ranker is not None else V1OptimizedRanker()
        self._lock = threading.Lock()
        self._telemetry: pd.DataFrame | None = None
        self._master: pd.DataFrame | None = None

    def get_health(self) -> dict[str, str]:
        """Return lightweight operational health status."""
        return {"status": "ok"}

    def _ensure_data_loaded(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Lazy-load and cache telemetry and gateway master datasets safely."""
        with self._lock:
            if self._telemetry is not None and self._master is not None:
                return self._telemetry, self._master

            if not self.data_dir.exists():
                raise DataNotFoundError(
                    f"Configured data directory does not exist: '{self.data_dir}'"
                )

            master_path = self.data_dir / "gateway_master.csv"
            telemetry_path = self.data_dir / "telemetry"

            if not master_path.exists():
                raise DataNotFoundError(f"Missing master data file: '{master_path}'")
            if not telemetry_path.exists():
                raise DataNotFoundError(f"Missing telemetry directory: '{telemetry_path}'")

            try:
                self._master = load_gateway_master(self.data_dir)
                if self.ranker.name == STRATEGY_OPTIMIZED:
                    self._telemetry = load_telemetry_extended(self.data_dir)
                else:
                    self._telemetry = load_telemetry(self.data_dir)
            except Exception as exc:
                raise PipelineExecutionError(f"Failed loading challenge data: {exc}") from exc

            return self._telemetry, self._master

    def parse_and_validate_week(self, week_input: str | dt.date) -> dt.date:
        """Parse an ISO date string or date object and verify it belongs to scored window."""
        if isinstance(week_input, dt.date):
            target_date = week_input
        else:
            try:
                target_date = dt.date.fromisoformat(str(week_input).strip())
            except ValueError as exc:
                raise InvalidWeekError(
                    f"Invalid date format '{week_input}'. Expected YYYY-MM-DD."
                ) from exc

        if target_date not in SCORED_WEEKS:
            valid_weeks = ", ".join(w.isoformat() for w in SCORED_WEEKS)
            raise InvalidWeekError(
                f"Week '{target_date.isoformat()}' is not a scored prediction week. "
                f"Scored weeks are: [{valid_weeks}]"
            )

        return target_date

    def get_predictions_for_week(
        self, week_input: str | dt.date
    ) -> dict[str, Any]:
        """Return exactly 15 recommended gateways for the specified week."""
        target_date = self.parse_and_validate_week(week_input)
        telemetry, master = self._ensure_data_loaded()

        df = self.ranker.predict_week(telemetry, master, target_date, limit=15)
        predictions = df.to_dict(orient="records")
        return {
            "week_start": target_date.isoformat(),
            "count": len(predictions),
            "predictions": predictions,
        }

    def explain_gateway(
        self,
        gateway_id: str,
        week_input: str | dt.date | None = None,
    ) -> dict[str, Any]:
        """Explain the ranking of a gateway for the requested or latest scored week."""
        if not gateway_id or not str(gateway_id).strip():
            raise InvalidWeekError("Gateway ID cannot be empty.")

        if week_input is None:
            target_date = SCORED_WEEKS[-1]
        else:
            target_date = self.parse_and_validate_week(week_input)

        telemetry, master = self._ensure_data_loaded()
        return self.ranker.explain_gateway(
            telemetry, master, target_date, gateway_id
        )

    def run_prediction(
        self,
        week_start: str | dt.date | None = None,
        output_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """Run the prediction pipeline either for a single week or all scored weeks."""
        telemetry, master = self._ensure_data_loaded()

        if week_start is not None:
            target_date = self.parse_and_validate_week(week_start)
            df = self.ranker.predict_week(telemetry, master, target_date, limit=15)
            weeks_predicted = [target_date.isoformat()]
        else:
            df = self.ranker.predict_all(telemetry, master, SCORED_WEEKS)
            weeks_predicted = [w.isoformat() for w in SCORED_WEEKS]

        if output_path is not None:
            out = Path(output_path)
            with self._lock:
                write_predictions(df, out)
            saved_to = str(out)
        else:
            saved_to = None

        return {
            "status": "success",
            "strategy": self.ranker.name,
            "weeks_predicted": weeks_predicted,
            "total_predictions": len(df),
            "output_path": saved_to,
            "predictions": df.to_dict(orient="records"),
        }

    def reload_data(self) -> None:
        """Force flush cached telemetry and master frames to reload from disk."""
        with self._lock:
            self._telemetry = None
            self._master = None
