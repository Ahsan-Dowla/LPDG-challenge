from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import OUTPUT_COLUMNS


def write_predictions(predictions: pd.DataFrame, path: Path) -> None:
    """Write only the public submission columns in their required order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    predictions.loc[:, OUTPUT_COLUMNS].to_csv(path, index=False)
