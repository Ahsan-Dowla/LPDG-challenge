"""Evaluation metrics and comparison methods for gateway visit ranking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.lpdg.config import DATA_DIR, OUTPUT_COLUMNS, SCORED_WEEKS
from src.lpdg.data.loaders import normalize_gateway_id


def evaluate_predictions(
    pred_path: Path | str,
    data_dir: Path | str = DATA_DIR,
) -> dict[str, Any]:
    """Evaluate a predictions CSV against independent engineer reviews and meter reads."""
    path = Path(pred_path)
    preds = pd.read_csv(path)
    preds["gateway_id"] = preds["gateway_id"].map(normalize_gateway_id)

    # Load engineer review snapshot
    eng_path = Path(data_dir) / "engineer_review_2026-02.xlsx"
    eng_map = {}
    if eng_path.exists():
        try:
            eng_df = pd.read_excel(eng_path)
            eng_df["gateway_id"] = eng_df["gateway_id"].map(normalize_gateway_id)
            eng_map = dict(zip(eng_df["gateway_id"], eng_df["Kategorie"]))
        except Exception:
            pass

    # Load historical meter read rates
    mrs_path = Path(data_dir) / "meter_read_success.csv"
    last_mrs = {}
    if mrs_path.exists():
        try:
            mrs = pd.read_csv(mrs_path)
            mrs["gateway_id"] = mrs["gateway_id"].map(normalize_gateway_id)
            mrs["read_rate"] = mrs["meters_read"] / mrs["meters_expected"].replace(0, np.nan)
            last_mrs = mrs.groupby("gateway_id")["read_rate"].last().to_dict()
        except Exception:
            pass

    # Load gateway master for installed meters
    gm_path = Path(data_dir) / "gateway_master.csv"
    meter_map = {}
    if gm_path.exists():
        try:
            gm = pd.read_csv(gm_path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            gm = pd.read_csv(gm_path, encoding="cp1252")
        except Exception:
            gm = pd.DataFrame()
        if not gm.empty:
            gm["gateway_id"] = gm["gateway_id"].map(normalize_gateway_id)
            meter_map = dict(zip(gm["gateway_id"], gm["n_meters_installed"]))

    total_rows = len(preds)
    preds["kategorie"] = preds["gateway_id"].map(eng_map)
    preds["last_read_rate"] = preds["gateway_id"].map(last_mrs)
    preds["n_meters"] = preds["gateway_id"].map(meter_map).fillna(0)

    # Visit-level metrics
    n_schlecht = int((preds["kategorie"] == "Schlecht").sum())
    n_normal = int((preds["kategorie"] == "Normal").sum())
    n_unreviewed = int(preds["kategorie"].isna().sum())
    sn_ratio = (n_schlecht / n_normal) if n_normal > 0 else float("inf")

    # Unique gateway metrics
    unique_gws = preds.drop_duplicates(subset=["gateway_id"])
    n_unique_gws = len(unique_gws)
    u_schlecht = int((unique_gws["kategorie"] == "Schlecht").sum())
    u_normal = int((unique_gws["kategorie"] == "Normal").sum())
    u_unreviewed = int(unique_gws["kategorie"].isna().sum())
    u_sn_ratio = (u_schlecht / u_normal) if u_normal > 0 else float("inf")

    valid_reads = preds["last_read_rate"].dropna()
    mean_read = float(valid_reads.mean()) if not valid_reads.empty else 0.0
    read_sub_90 = int((preds["last_read_rate"] < 0.90).sum())
    read_sub_80 = int((preds["last_read_rate"] < 0.80).sum())
    total_meters = int(preds["n_meters"].sum())
    mean_meters = float(preds["n_meters"].mean()) if total_rows > 0 else 0.0

    return {
        "file": path.name,
        "total_rows": total_rows,
        "n_unique_gws": n_unique_gws,
        "n_schlecht": n_schlecht,
        "n_normal": n_normal,
        "n_unreviewed": n_unreviewed,
        "sn_ratio": sn_ratio,
        "u_schlecht": u_schlecht,
        "u_normal": u_normal,
        "u_unreviewed": u_unreviewed,
        "u_sn_ratio": u_sn_ratio,
        "mean_read_rate": mean_read,
        "reads_below_90pct": read_sub_90,
        "reads_below_80pct": read_sub_80,
        "total_meters_exposed": total_meters,
        "mean_meters_per_visit": mean_meters,
    }


def calc_brier_score(
    predicted_probabilities: pd.Series | np.ndarray,
    binary_outcomes: pd.Series | np.ndarray,
) -> float:
    """Compute Brier score (mean squared error of probabilistic predictions)."""
    p = np.asarray(predicted_probabilities, dtype=float)
    y = np.asarray(binary_outcomes, dtype=float)
    return float(np.mean((p - y) ** 2))
