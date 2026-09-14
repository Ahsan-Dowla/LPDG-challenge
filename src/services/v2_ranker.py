"""V2 Probabilistic Ranker adapter implementing BaseRanker."""

from __future__ import annotations

from src.lpdg.config import STRATEGY_V2
from src.lpdg.ranking.v2 import V2Ranker


class V2ProbabilisticRanker(V2Ranker):
    """Production adapter wrapping the Probabilistic & Expected-Value V2 ranker."""

    @property
    def name(self) -> str:
        return STRATEGY_V2


__all__ = ["V2ProbabilisticRanker"]
