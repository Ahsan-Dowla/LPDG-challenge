from __future__ import annotations

from pathlib import Path

from .config import STRATEGY_BASELINE, STRATEGY_OPTIMIZED, STRATEGY_V2, DEFAULT_STRATEGY
from .data_loader import load_gateway_master, load_telemetry, load_telemetry_extended
from .output import write_predictions
from .ranker import build_predictions as build_predictions_baseline
from .ranker_optimized import build_predictions_optimized
from .ranker_v2 import build_predictions_v2


def run(data_dir: Path, output_path: Path, strategy: str = DEFAULT_STRATEGY):
    """Run the complete Part 1 pipeline from source data to CSV.

    Parameters
    ----------
    data_dir:
        Directory containing all challenge data (telemetry/, gateway_master.csv, …).
    output_path:
        Destination path for predictions.csv.
    strategy:
        ``"baseline"``  – original 3-sigma anomaly-count ranker (unchanged).
        ``"optimized"`` – Optimization V1 (technical severity + persistence +
                          corroboration + exposure).
        ``"v2"``         – Probabilistic V2 (robust statistics + Bayesian
                          persistence + expected-value decision score).
    """
    strategy = strategy.strip().lower()
    valid_strategies = (STRATEGY_BASELINE, STRATEGY_OPTIMIZED, STRATEGY_V2)
    if strategy not in valid_strategies:
        raise ValueError(
            f"unknown strategy {strategy!r}; choose one of {valid_strategies!r}"
        )

    master = load_gateway_master(data_dir)

    if strategy == STRATEGY_BASELINE:
        telemetry = load_telemetry(data_dir)
        predictions = build_predictions_baseline(telemetry, master)
    elif strategy == STRATEGY_OPTIMIZED:
        telemetry = load_telemetry_extended(data_dir)
        predictions = build_predictions_optimized(telemetry, master)
    elif strategy == STRATEGY_V2:
        telemetry = load_telemetry_extended(data_dir)
        predictions = build_predictions_v2(telemetry, master)
    else:
        raise ValueError(
            f"unknown strategy {strategy!r}; choose one of {valid_strategies!r}"
        )

    write_predictions(predictions, output_path)
    return predictions
