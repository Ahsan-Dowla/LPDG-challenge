#!/usr/bin/env python3
"""Generate the deterministic Part 1 weekly gateway visit ranking."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.part1.pipeline import run


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=here / "data")
    parser.add_argument("--out", type=Path, default=here / "predictions.csv")
    args = parser.parse_args(argv)

    predictions = run(args.data, args.out)
    print(
        f"wrote {args.out} - {len(predictions)} rows over "
        f"{predictions['week_start'].nunique()} weeks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
