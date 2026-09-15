"""Features layer package for LPDG."""

from .telemetry import (
    calc_baseline_3sigma_thresholds,
    calc_bayesian_persistence,
    calc_coverage_and_silence,
    calc_raw_persistence,
    norm_by_max,
    robust_z_pos,
)

__all__ = [
    "calc_baseline_3sigma_thresholds",
    "calc_bayesian_persistence",
    "calc_coverage_and_silence",
    "calc_raw_persistence",
    "norm_by_max",
    "robust_z_pos",
]
