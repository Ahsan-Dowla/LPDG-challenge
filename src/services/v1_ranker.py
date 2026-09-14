"""V1 Optimized Ranker adapter implementing BaseRanker."""

from __future__ import annotations

from src.lpdg.config import STRATEGY_OPTIMIZED
from src.lpdg.ranking.v1 import V1Ranker


class V1OptimizedRanker(V1Ranker):
    """Production adapter wrapping the Part 1 frozen Optimization V1 ranker."""

    @property
    def name(self) -> str:
        return STRATEGY_OPTIMIZED


__all__ = ["V1OptimizedRanker"]

