"""Domain service coordinating dataset ingestion, strategy selection, and ranking."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
import threading
from typing import Any

import pandas as pd

from src.lpdg.config import (
    DATA_DIR,
    DEFAULT_STRATEGY,
    SCORED_WEEKS,
    STRATEGY_BASELINE,
    STRATEGY_OPTIMIZED,
    STRATEGY_V1,
    STRATEGY_V2,
)
from src.lpdg.data.loaders import (
    load_gateway_master,
    load_telemetry,
    load_telemetry_extended,
    write_predictions,
)
from src.lpdg.exceptions import (
    DataNotFoundError,
    InvalidStrategyError,
    InvalidWeekError,
    PipelineExecutionError,
)
from src.lpdg.ranking.baseline import BaselineRanker
from src.lpdg.ranking.interfaces import RankingStrategy
from src.lpdg.ranking.v1 import V1Ranker
from src.lpdg.ranking.v2 import V2Ranker

logger = logging.getLogger("lpdg.ranking.service")


class RankingService:
    """Service layer encapsulating dataset management and ranking operations."""

    def __init__(
        self,
        data_dir: Path | str = DATA_DIR,
        strategy: str | RankingStrategy | None = None,
        ranker: RankingStrategy | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        chosen = strategy if strategy is not None else ranker
        self.strategy = self._resolve_strategy(chosen)
        self._lock = threading.Lock()
        self._telemetry: pd.DataFrame | None = None
        self._master: pd.DataFrame | None = None
        logger.info(
            "RankingService initialized (data_dir='%s', strategy='%s')",
            self.data_dir,
            self.strategy.name,
        )

    @property
    def ranker(self) -> RankingStrategy:
        """Alias for backward compatibility with earlier adapters."""
        return self.strategy

    def _resolve_strategy(self, strategy: str | RankingStrategy | None) -> RankingStrategy:
        """Resolve a strategy instance from name or object."""
        if strategy is None:
            strategy_name = DEFAULT_STRATEGY
        elif isinstance(strategy, RankingStrategy):
            return strategy
        elif isinstance(strategy, str):
            strategy_name = strategy.strip().lower()
        else:
            raise InvalidStrategyError(f"Unsupported strategy argument: {strategy}")

        if strategy_name == STRATEGY_BASELINE:
            return BaselineRanker()
        elif strategy_name in (STRATEGY_V1, STRATEGY_OPTIMIZED):
            return V1Ranker()
        elif strategy_name == STRATEGY_V2:
            return V2Ranker()
        else:
            raise InvalidStrategyError(
                f"Unknown strategy {strategy_name!r}; choose 'v1', 'v2', or 'baseline'"
            )

    def set_strategy(self, strategy: str | RankingStrategy) -> None:
        """Switch the active ranking strategy."""
        with self._lock:
            self.strategy = self._resolve_strategy(strategy)
            # Invalidate cached telemetry if strategy requirement changes
            self._telemetry = None
            logger.info("RankingService switched strategy to '%s'", self.strategy.name)

    def get_health(self) -> dict[str, str]:
        """Return operational health status."""
        return {"status": "ok"}

    def _ensure_data_loaded(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Lazy-load and cache telemetry and master frames safely."""
        with self._lock:
            if self._telemetry is not None and self._master is not None:
                return self._telemetry, self._master

            if not self.data_dir.exists():
                raise DataNotFoundError(
                    f"Configured data directory does not exist: '{self.data_dir}'"
                )

            try:
                self._master = load_gateway_master(self.data_dir)
                if self.strategy.name in (STRATEGY_V1, STRATEGY_OPTIMIZED, STRATEGY_V2):
                    self._telemetry = load_telemetry_extended(self.data_dir)
                else:
                    self._telemetry = load_telemetry(self.data_dir)
                logger.info(
                    "Loaded challenge data (master=%d gateways, telemetry=%d rows)",
                    len(self._master),
                    len(self._telemetry),
                )
            except DataNotFoundError:
                raise
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

        logger.info("Generating predictions for week %s with strategy %s", target_date, self.strategy.name)
        df = self.strategy.predict_week(telemetry, master, target_date, limit=15)
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

        target_date = (
            SCORED_WEEKS[-1]
            if week_input is None
            else self.parse_and_validate_week(week_input)
        )

        telemetry, master = self._ensure_data_loaded()
        return self.strategy.explain_gateway(
            telemetry, master, target_date, gateway_id
        )

    def run_prediction(
        self,
        week_start: str | dt.date | None = None,
        output_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """Run prediction pipeline for a single week or all scored weeks."""
        telemetry, master = self._ensure_data_loaded()

        if week_start is not None:
            target_date = self.parse_and_validate_week(week_start)
            df = self.strategy.predict_week(telemetry, master, target_date, limit=15)
            weeks_predicted = [target_date.isoformat()]
        else:
            df = self.strategy.predict_all(telemetry, master, SCORED_WEEKS)
            weeks_predicted = [w.isoformat() for w in SCORED_WEEKS]

        saved_to = None
        if output_path is not None:
            out = Path(output_path)
            with self._lock:
                write_predictions(df, out)
            saved_to = str(out)
            logger.info("Saved %d predictions to %s", len(df), saved_to)

        return {
            "status": "success",
            "strategy": self.strategy.name,
            "weeks_predicted": weeks_predicted,
            "total_predictions": len(df),
            "output_path": saved_to,
            "predictions": df.to_dict(orient="records"),
        }

    def predict_all(self) -> pd.DataFrame:
        """Generate full predictions DataFrame across all scored weeks."""
        telemetry, master = self._ensure_data_loaded()
        return self.strategy.predict_all(telemetry, master, SCORED_WEEKS)

    def reload_data(self) -> None:
        """Flush cached telemetry and master frames to force reload from disk."""
        with self._lock:
            self._telemetry = None
            self._master = None
            logger.info("RankingService cached data flushed.")
