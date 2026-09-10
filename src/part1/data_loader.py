from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import EXTRA_TELEMETRY_COLS, METRICS


def normalize_gateway_id(value: object) -> str:
    """Return the canonical compact, uppercase gateway identifier."""
    return str(value).strip().replace(":", "").upper()


def load_telemetry(data_dir: Path) -> pd.DataFrame:
    """Load complete partitioned telemetry, normalize IDs, and remove exact duplicates.

    Loads the baseline METRICS columns only.  Call ``load_telemetry_extended``
    when the optimized ranker's additional signal columns are also needed.
    """
    frame = pd.read_parquet(
        data_dir / "telemetry", columns=["gateway_id", "ts_utc", *METRICS]
    )
    frame["gateway_id"] = frame["gateway_id"].map(normalize_gateway_id)
    frame["ts"] = pd.to_datetime(frame.pop("ts_utc"), utc=True)
    frame = frame.drop_duplicates(subset=["gateway_id", "ts"], keep="first")
    return frame


def load_telemetry_extended(data_dir: Path) -> pd.DataFrame:
    """Like ``load_telemetry`` but also includes EXTRA_TELEMETRY_COLS for the optimized ranker."""
    frame = pd.read_parquet(
        data_dir / "telemetry",
        columns=["gateway_id", "ts_utc", *METRICS, *EXTRA_TELEMETRY_COLS],
    )
    frame["gateway_id"] = frame["gateway_id"].map(normalize_gateway_id)
    frame["ts"] = pd.to_datetime(frame.pop("ts_utc"), utc=True)
    frame = frame.drop_duplicates(subset=["gateway_id", "ts"], keep="first")
    return frame


def load_gateway_master(data_dir: Path) -> pd.DataFrame:
    """Load the master file, handling the supplied German cp1252 export."""
    path = data_dir / "gateway_master.csv"
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        frame = pd.read_csv(path, encoding="cp1252")
    frame["gateway_id"] = frame["gateway_id"].map(normalize_gateway_id)
    for column in ("installed_on", "decommissioned_on"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.date
    return frame

