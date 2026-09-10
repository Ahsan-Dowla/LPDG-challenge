#!/usr/bin/env python3
"""Generate the deterministic Part 1 weekly gateway visit ranking.

Usage examples::

    python main.py                                        # optimized (default)
    python main.py --strategy optimized                   # explicit default
    python main.py --strategy baseline                    # 3-sigma baseline
    python main.py --data /path/to/data --out out.csv     # custom paths
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.part1.config import DEFAULT_STRATEGY, STRATEGY_BASELINE, STRATEGY_OPTIMIZED
from src.part1.pipeline import run


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=here / "data")
    parser.add_argument("--out", type=Path, default=here / "predictions.csv")
    parser.add_argument(
        "--strategy",
        choices=[STRATEGY_BASELINE, STRATEGY_OPTIMIZED],
        default=DEFAULT_STRATEGY,
        help=(
            f"Ranking strategy to use. "
            f"'{STRATEGY_BASELINE}': original 3-sigma anomaly-count ranker. "
            f"'{STRATEGY_OPTIMIZED}': Optimization V1 (technical severity + "
            f"persistence + corroboration + exposure). Default: {DEFAULT_STRATEGY}."
        ),
    )
    args = parser.parse_args(argv)

    predictions = run(args.data, args.out, strategy=args.strategy)
    print(
        f"[{args.strategy}] wrote {args.out} — {len(predictions)} rows over "
        f"{predictions['week_start'].nunique()} weeks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
