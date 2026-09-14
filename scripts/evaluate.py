#!/usr/bin/env python3
"""Evaluate prediction outputs against historical field visit records.

Computes per-week and overall hit metrics:
  - hit_rate: fraction of top-15 visits that resulted in a confirmed engineer review
  - meter_read_hit_rate: fraction with meter_read < 80% (proxy for impairment)

Usage::

    venv\Scripts\python scripts\evaluate.py --pred predictions.csv
    venv\Scripts\python scripts\evaluate.py --pred outputs\predictions_v2.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.lpdg.config import DATA_DIR, SCORED_WEEKS, VISITS_PER_WEEK


def load_field_visits(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "field_visit_outcomes.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_meter_reads(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "meter_read_success.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    return df


def evaluate(pred_path: Path, data_dir: Path) -> None:
    pred = pd.read_csv(pred_path)
    pred.columns = [c.lower() for c in pred.columns]

    fv = load_field_visits(data_dir)
    mr = load_meter_reads(data_dir)

    if fv.empty and mr.empty:
        print("No outcome data found in data directory — cannot evaluate.")
        return

    rows = []
    for week in sorted(pred["week_start"].unique()):
        top15 = set(pred[pred["week_start"] == week]["gateway_id"])

        fv_hit, fv_denom = 0, 0
        if not fv.empty and "week_start" in fv.columns and "gateway_id" in fv.columns:
            wfv = fv[fv["week_start"] == week]
            fv_denom = len(wfv)
            fv_hit = wfv[wfv["gateway_id"].isin(top15)].shape[0] if fv_denom else 0

        mr_hit, mr_denom = 0, 0
        if not mr.empty and "gateway_id" in mr.columns:
            wmr = mr[mr.get("week_start", pd.Series(dtype=str)) == week] if "week_start" in mr.columns else mr
            below80 = wmr[wmr.get("read_success_pct", wmr.get("meter_read_pct", pd.Series(dtype=float))) < 0.8]
            mr_denom = len(below80)
            mr_hit = below80[below80["gateway_id"].isin(top15)].shape[0] if mr_denom else 0

        rows.append({
            "week": week,
            "top15_in_fv": fv_hit if fv_denom else "n/a",
            "fv_total": fv_denom if fv_denom else "n/a",
            "mr_impaired_hit": mr_hit if mr_denom else "n/a",
            "mr_impaired_total": mr_denom if mr_denom else "n/a",
        })

    result = pd.DataFrame(rows)
    print(f"\n=== Evaluation: {pred_path.name} ===")
    print(result.to_string(index=False))
    print(f"\nTotal weeks: {len(result)}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pred", type=Path, default=Path("predictions.csv"))
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)
    evaluate(args.pred, args.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
