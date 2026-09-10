from __future__ import annotations

from pathlib import Path

from .data_loader import load_gateway_master, load_telemetry
from .output import write_predictions
from .ranker import build_predictions


def run(data_dir: Path, output_path: Path):
    """Run the complete Part 1 pipeline from source data to CSV."""
    telemetry = load_telemetry(data_dir)
    master = load_gateway_master(data_dir)
    predictions = build_predictions(telemetry, master)
    write_predictions(predictions, output_path)
    return predictions
