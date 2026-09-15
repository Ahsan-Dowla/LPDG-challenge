#!/usr/bin/env python3
"""Walk-forward backtest over the 8 scored weeks.

For each Monday cutoff, ranks gateways using data strictly available
before that cutoff (no future data leakage), then measures overlap
with the official frozen predictions to confirm reproducibility.

Usage::

    venv\Scripts\python scripts\backtest.py
    venv\Scripts\python scripts\backtest.py --strategy v2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.lpdg.config import DATA_DIR, SCORED_WEEKS, STRATEGY_OPTIMIZED, STRATEGY_V2
from src.lpdg.ranking.service import RankingService
from src.lpdg.ranking.v1 import V1Ranker
from src.lpdg.ranking.v2 import V2Ranker


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument(
        "--strategy",
        choices=[STRATEGY_OPTIMIZED, "v1", STRATEGY_V2],
        default=STRATEGY_OPTIMIZED,
    )
    parser.add_argument("--ref", type=Path, default=None, help="Reference CSV to measure overlap against")
    args = parser.parse_args(argv)

    ranker = V2Ranker() if args.strategy == STRATEGY_V2 else V1Ranker()
    svc = RankingService(data_dir=args.data, strategy=ranker)

    ref = None
    if args.ref and args.ref.exists():
        ref = pd.read_csv(args.ref)

    print(f"=== Walk-Forward Backtest: {args.strategy.upper()} ===")
    print(f"{'Week':<12} {'Top-1 Gateway':<16} {'Score':>8}  {'Overlap/15':>10}")
    print("-" * 60)

    for week in SCORED_WEEKS:
        result = svc.get_predictions_for_week(week)
        preds = result["predictions"]
        top1 = preds[0]

        overlap_str = ""
        if ref is not None:
            ref_set = set(ref[ref["week_start"] == week.isoformat()]["gateway_id"])
            pred_set = {p["gateway_id"] for p in preds}
            overlap = len(ref_set & pred_set)
            overlap_str = f"{overlap:>10}/15"

        print(f"{week.isoformat():<12} {top1['gateway_id']:<16} {top1['score']:>8.4f}  {overlap_str}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

