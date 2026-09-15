"""Data loading, normalization, and validation for LPDG datasets."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import re
from typing import Sequence

import pandas as pd

from src.lpdg.config import (
    DATA_DIR,
    EXTRA_TELEMETRY_COLS,
    METRICS,
    OUTPUT_COLUMNS,
    SCORED_WEEKS,
    VISITS_PER_WEEK,
)
from src.lpdg.exceptions import DataNotFoundError


def normalize_gateway_id(raw: str) -> str:
    """Normalize a gateway ID into standard uppercase 12-char hex without colons."""
    if not isinstance(raw, str):
        raw = str(raw)
    cleaned = re.sub(r"[^A-Fa-f0-9]", "", raw.strip())
    return cleaned.upper()


def load_telemetry(
    data_dir: Path | str = DATA_DIR,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load core telemetry dataset across all monthly Parquet partitions.

    Deduplicates exact (gateway_id, ts) pairs keeping the first row.
    """
    telemetry_dir = Path(data_dir) / "telemetry"
    if not telemetry_dir.exists():
        raise DataNotFoundError(f"Telemetry directory not found: {telemetry_dir}")

    target_cols = list(columns) if columns else ["gateway_id", "ts_utc"] + METRICS
    try:
        df = pd.read_parquet(telemetry_dir, columns=target_cols)
    except Exception as exc:
        raise DataNotFoundError(f"Failed to read parquet telemetry at {telemetry_dir}: {exc}") from exc

    df["gateway_id"] = df["gateway_id"].map(normalize_gateway_id)
    df["ts"] = pd.to_datetime(df["ts_utc"], utc=True)
    df = df.drop(columns=["ts_utc"])

    # Remove exact duplicate gateway-timestamp records
    df = df.drop_duplicates(subset=["gateway_id", "ts"], keep="first")
    return df


def load_telemetry_extended(data_dir: Path | str = DATA_DIR) -> pd.DataFrame:
    """Load telemetry including additional corroborating columns (e.g. no_conn_importance)."""
    cols = ["gateway_id", "ts_utc"] + METRICS + EXTRA_TELEMETRY_COLS
    return load_telemetry(data_dir, columns=cols)


def load_gateway_master(data_dir: Path | str = DATA_DIR) -> pd.DataFrame:
    """Load and normalize the gateway master asset register."""
    master_path = Path(data_dir) / "gateway_master.csv"
    if not master_path.exists():
        raise DataNotFoundError(f"Gateway master file not found: {master_path}")

    try:
        master = pd.read_csv(master_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        master = pd.read_csv(master_path, encoding="cp1252")
    except Exception as exc:
        raise DataNotFoundError(f"Failed to read gateway master at {master_path}: {exc}") from exc

    master["gateway_id"] = master["gateway_id"].map(normalize_gateway_id)
    master["installed_on"] = pd.to_datetime(master["installed_on"], errors="coerce").dt.date
    master["decommissioned_on"] = pd.to_datetime(master["decommissioned_on"], errors="coerce").dt.date
    return master


def active_gateways(master: pd.DataFrame, cutoff: dt.date | pd.Timestamp) -> set[str]:
    """Return canonical gateway IDs active at the given Monday cutoff date.

    Eligibility rules:
      1. Commissioned on or before cutoff date (missing installation date is eligible).
      2. NOT decommissioned on or before cutoff date.
    """
    cutoff_date = cutoff.date() if isinstance(cutoff, (pd.Timestamp, dt.datetime)) else cutoff
    inst = master["installed_on"].apply(lambda x: x.date() if isinstance(x, (pd.Timestamp, dt.datetime)) else x)
    decom = master["decommissioned_on"].apply(lambda x: x.date() if isinstance(x, (pd.Timestamp, dt.datetime)) else x)

    installed = inst.isna() | (inst <= cutoff_date)
    decommissioned = decom.notna() & (decom <= cutoff_date)
    return set(master.loc[installed & ~decommissioned, "gateway_id"])


def write_predictions(predictions: pd.DataFrame, output_path: Path | str) -> Path:
    """Write predictions DataFrame to CSV enforcing required schema and ordering."""
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out_df = predictions[OUTPUT_COLUMNS].copy()
    out_df.to_csv(dest, index=False)
    return dest


def validate_prediction_dataframe(df: pd.DataFrame) -> None:
    """Validate that a predictions DataFrame satisfies all Part 1 submission rules."""
    if list(df.columns) != OUTPUT_COLUMNS:
        raise ValueError(f"Columns mismatch: expected {OUTPUT_COLUMNS}, got {list(df.columns)}")

    expected_rows = len(SCORED_WEEKS) * VISITS_PER_WEEK
    if len(df) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, got {len(df)}")

    for week, group in df.groupby("week_start"):
        if len(group) != VISITS_PER_WEEK:
            raise ValueError(f"Week {week} has {len(group)} rows, expected {VISITS_PER_WEEK}")
        if sorted(group["rank"].tolist()) != list(range(1, VISITS_PER_WEEK + 1)):
            raise ValueError(f"Week {week} ranks are not 1 to {VISITS_PER_WEEK}")
        if group["gateway_id"].nunique() != VISITS_PER_WEEK:
            raise ValueError(f"Week {week} contains duplicate gateway IDs")
        for reason in group["reason"]:
            if not isinstance(reason, str) or len(reason) == 0 or len(reason) > 300:
                raise ValueError(f"Invalid reason length ({len(str(reason))} chars): {reason[:30]}...")
