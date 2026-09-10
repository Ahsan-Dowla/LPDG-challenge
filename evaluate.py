"""Evaluation and backtesting script for Part 1 gateway visit rankings.

Compares ranking predictions against ground-truth/proxy business signals:
  1. Engineer Review (Kategorie: Schlecht vs Normal, Feb 2026 snapshot)
  2. Historical Meter Read Rates (meters_read / meters_expected)
  3. Installed Meter Impact (total meters exposed at visited sites)

Usage:
  python evaluate.py predictions_optimized.csv
  python evaluate.py predictions_baseline.csv
  python evaluate.py --compare predictions_baseline.csv predictions_optimized.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.part1.data_loader import normalize_gateway_id


def evaluate_predictions(pred_path: Path, data_dir: Path) -> dict[str, object]:
    preds = pd.read_csv(pred_path)
    preds["gateway_id"] = preds["gateway_id"].map(normalize_gateway_id)

    # Load engineer review if available
    eng_path = data_dir / "engineer_review_2026-02.xlsx"
    eng_df = None
    if eng_path.exists():
        eng_df = pd.read_excel(eng_path)
        eng_df["gateway_id"] = eng_df["gateway_id"].map(normalize_gateway_id)
        eng_map = dict(zip(eng_df["gateway_id"], eng_df["Kategorie"]))
    else:
        eng_map = {}

    # Load meter reads
    mrs_path = data_dir / "meter_read_success.csv"
    if mrs_path.exists():
        mrs = pd.read_csv(mrs_path)
        mrs["gateway_id"] = mrs["gateway_id"].map(normalize_gateway_id)
        mrs["read_rate"] = mrs["meters_read"] / mrs["meters_expected"].replace(0, np.nan)
        last_mrs = mrs.groupby("gateway_id")["read_rate"].last().to_dict()
    else:
        last_mrs = {}

    # Load gateway master for installed meters
    gm_path = data_dir / "gateway_master.csv"
    if gm_path.exists():
        try:
            gm = pd.read_csv(gm_path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            gm = pd.read_csv(gm_path, encoding="cp1252")
        gm["gateway_id"] = gm["gateway_id"].map(normalize_gateway_id)
        meter_map = dict(zip(gm["gateway_id"], gm["n_meters_installed"]))
    else:
        meter_map = {}

    total_rows = len(preds)
    preds["kategorie"] = preds["gateway_id"].map(eng_map)
    preds["last_read_rate"] = preds["gateway_id"].map(last_mrs)
    preds["n_meters"] = preds["gateway_id"].map(meter_map).fillna(0)

    n_schlecht = int((preds["kategorie"] == "Schlecht").sum())
    n_normal = int((preds["kategorie"] == "Normal").sum())
    n_unreviewed = int(preds["kategorie"].isna().sum())
    sn_ratio = (n_schlecht / n_normal) if n_normal > 0 else float("inf")

    mean_read = float(preds["last_read_rate"].dropna().mean()) if not preds["last_read_rate"].dropna().empty else 0.0
    read_sub_90 = int((preds["last_read_rate"] < 0.90).sum())
    read_sub_80 = int((preds["last_read_rate"] < 0.80).sum())
    total_meters = int(preds["n_meters"].sum())
    mean_meters = float(preds["n_meters"].mean())

    return {
        "file": pred_path.name,
        "total_rows": total_rows,
        "n_schlecht": n_schlecht,
        "n_normal": n_normal,
        "n_unreviewed": n_unreviewed,
        "sn_ratio": sn_ratio,
        "mean_read_rate": mean_read,
        "reads_below_90pct": read_sub_90,
        "reads_below_80pct": read_sub_80,
        "total_meters_exposed": total_meters,
        "mean_meters_per_visit": mean_meters,
    }


def print_metrics(m: dict[str, object]) -> None:
    print(f"=== Evaluation: {m['file']} ===")
    print(f"Total rows:             {m['total_rows']}")
    print(f"Engineer 'Schlecht':    {m['n_schlecht']}")
    print(f"Engineer 'Normal':      {m['n_normal']}")
    print(f"Engineer Unreviewed:    {m['n_unreviewed']}")
    sn_str = f"{m['sn_ratio']:.2f}" if m['sn_ratio'] != float("inf") else "inf"
    print(f"Signal-to-Noise (S/N):  {sn_str}")
    print(f"Mean Last Read Rate:    {m['mean_read_rate']:.4f}")
    print(f"Visits with Read < 90%: {m['reads_below_90pct']} / {m['total_rows']}")
    print(f"Visits with Read < 80%: {m['reads_below_80pct']} / {m['total_rows']}")
    print(f"Total Meters Exposed:   {m['total_meters_exposed']:,}")
    print(f"Mean Meters per Visit:  {m['mean_meters_per_visit']:.1f}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate gateway ranking predictions")
    parser.add_argument("predictions", nargs="*", type=Path, help="Path(s) to predictions CSV file(s)")
    parser.add_argument("--data", type=Path, default=Path(__file__).parent / "data", help="Path to data directory")
    parser.add_argument("--compare", nargs=2, type=Path, help="Compare two prediction files side-by-side")
    args = parser.parse_args()

    data_dir = args.data

    if args.compare:
        m1 = evaluate_predictions(args.compare[0], data_dir)
        m2 = evaluate_predictions(args.compare[1], data_dir)
        print_metrics(m1)
        print_metrics(m2)
        print("=== Comparison Summary ===")
        print(f"{'Metric':<25} {m1['file']:<25} {m2['file']:<25}")
        print("-" * 75)
        print(f"{'Schlecht (Target)':<25} {m1['n_schlecht']:<25} {m2['n_schlecht']:<25}")
        print(f"{'Normal (False Alarm)':<25} {m1['n_normal']:<25} {m2['n_normal']:<25}")
        sn1 = f"{m1['sn_ratio']:.2f}" if m1['sn_ratio'] != float('inf') else "inf"
        sn2 = f"{m2['sn_ratio']:.2f}" if m2['sn_ratio'] != float('inf') else "inf"
        print(f"{'S/N Ratio':<25} {sn1:<25} {sn2:<25}")
        print(f"{'Mean Read Rate':<25} {m1['mean_read_rate']:<25.4f} {m2['mean_read_rate']:<25.4f}")
        print(f"{'Reads < 80%':<25} {m1['reads_below_80pct']:<25} {m2['reads_below_80pct']:<25}")
        print(f"{'Total Meters Exposed':<25} {m1['total_meters_exposed']:<25,} {m2['total_meters_exposed']:<25,}")
        return

    paths = args.predictions or [Path(__file__).parent / "predictions.csv"]
    for path in paths:
        m = evaluate_predictions(path, data_dir)
        print_metrics(m)


if __name__ == "__main__":
    main()
