#!/usr/bin/env python3
"""Generate the deterministic Part 1 weekly gateway visit ranking.

Usage examples::

    python main.py                                   # v1/optimized (default)
    python main.py --strategy v1                     # V1 explicit (canonical name)
    python main.py --strategy optimized              # V1 alias (backward compat)
    python main.py --strategy v2 --out predictions_v2.csv
    python main.py --strategy baseline
    python main.py --data /path/to/data --out out.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.part1.config import (
    DEFAULT_STRATEGY,
    STRATEGY_BASELINE,
    STRATEGY_OPTIMIZED,
    STRATEGY_V2,
)
from src.part1.pipeline import run

# v1 is the canonical name for the optimized strategy
STRATEGY_V1 = "v1"


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=here / "data")
    parser.add_argument("--out", type=Path, default=here / "predictions.csv")
    parser.add_argument(
        "--strategy",
        choices=[STRATEGY_BASELINE, STRATEGY_V1, STRATEGY_OPTIMIZED, STRATEGY_V2],
        default=DEFAULT_STRATEGY,
        help=(
            f"Ranking strategy to use. "
            f"'v1' (or 'optimized'): Official Part 1 strategy -- Optimized Evidence "
            f"(technical severity + persistence + corroboration + exposure). "
            f"'baseline': Original 3-sigma anomaly-count ranker. "
            f"'v2': Probabilistic V2 challenger (robust stats + Bayesian persistence "
            f"+ expected-value decision score). Default: {DEFAULT_STRATEGY}."
        ),
    )
    args = parser.parse_args(argv)

    # Treat v1 as an alias for optimized (same frozen pipeline)
    strategy = STRATEGY_OPTIMIZED if args.strategy == STRATEGY_V1 else args.strategy

    predictions = run(args.data, args.out, strategy=strategy)
    label = "v1" if strategy == STRATEGY_OPTIMIZED else strategy
    print(
        f"[{label}] wrote {args.out} -- {len(predictions)} rows over "
        f"{predictions['week_start'].nunique()} weeks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())