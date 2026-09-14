#!/usr/bin/env python3
"""Generate weekly gateway visit rankings.

This script is the canonical entrypoint for producing the submission output.
By default it runs the frozen V1 (Optimized) strategy — the official Part 1 answer.

Usage::

    venv\Scripts\python scripts\predict.py
    venv\Scripts\python scripts\predict.py --strategy v2 --out outputs\predictions_v2.csv
    venv\Scripts\python scripts\predict.py --strategy baseline
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.lpdg.config import (
    DATA_DIR,
    DEFAULT_STRATEGY,
    OUTPUT_DIR,
    STRATEGY_BASELINE,
    STRATEGY_OPTIMIZED,
    STRATEGY_V1,
    STRATEGY_V2,
)
from src.lpdg.ranking.service import RankingService
from src.lpdg.ranking.v1 import V1Ranker
from src.lpdg.ranking.v2 import V2Ranker
from src.lpdg.ranking.baseline import BaselineRanker
from src.lpdg.data.loaders import write_predictions


def build_ranker(strategy: str):
    s = strategy.strip().lower()
    if s in (STRATEGY_V1, STRATEGY_OPTIMIZED):
        return V1Ranker()
    elif s == STRATEGY_V2:
        return V2Ranker()
    elif s == STRATEGY_BASELINE:
        return BaselineRanker()
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="Data directory")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: outputs/predictions.csv or outputs/predictions_v2.csv)",
    )
    parser.add_argument(
        "--strategy",
        choices=[STRATEGY_BASELINE, STRATEGY_OPTIMIZED, STRATEGY_V1, STRATEGY_V2],
        default=DEFAULT_STRATEGY,
    )
    args = parser.parse_args(argv)

    out_file = args.out
    if out_file is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if args.strategy == STRATEGY_V2:
            out_file = OUTPUT_DIR / "predictions_v2.csv"
        elif args.strategy == STRATEGY_BASELINE:
            out_file = OUTPUT_DIR / "predictions_baseline.csv"
        else:
            out_file = OUTPUT_DIR / "predictions.csv"

    ranker = build_ranker(args.strategy)
    svc = RankingService(data_dir=args.data, strategy=ranker)
    df = svc.predict_all()
    write_predictions(df, out_file)

    print(f"[{args.strategy}] {out_file} — {len(df)} rows, {df['week_start'].nunique()} weeks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

