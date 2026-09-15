"""Feature extraction methods for telemetry anomalies, persistence, and coverage."""

from __future__ import annotations

import numpy as np
import pandas as pd


def norm_by_max(series: pd.Series) -> pd.Series:
    """Divide series by its maximum value; returns zeros if max is zero or NaN."""
    m = series.max()
    if m == 0 or pd.isna(m):
        return series * 0.0
    return series / m


def robust_z_pos(series: pd.Series, eps: float = 1.0) -> pd.Series:
    """Compute robust positive z-scores using Median and Median Absolute Deviation (MAD).

    Formula:
        z = (x - median) / (1.4826 * MAD + eps)
        z_pos = max(0, z)
        scaled = z_pos / max(z_pos)

    Normalized to [0, 1] relative to the active network maximum.
    """
    med = series.median()
    mad = np.median(np.abs(series - med))
    scale = 1.4826 * mad
    if scale == 0 or np.isnan(scale):
        raw_z = (series - med) / eps
    else:
        raw_z = (series - med) / scale

    # Only positive deviations represent degradation
    pos_z = np.maximum(0.0, raw_z)
    max_z = pos_z.max()
    if max_z > 0 and not np.isnan(max_z):
        return pos_z / max_z
    return pos_z * 0.0


def calc_baseline_3sigma_thresholds(
    baseline_telemetry: pd.DataFrame,
    metrics: list[str],
) -> pd.DataFrame:
    """Compute gateway-specific mean and standard deviation over trailing baseline window."""
    agg_funcs = {}
    for m in metrics:
        agg_funcs[f"{m}_mean"] = (m, "mean")
        agg_funcs[f"{m}_std"] = (m, "std")
    return baseline_telemetry.groupby("gateway_id").agg(**agg_funcs)


def calc_raw_persistence(
    problem_hours: pd.Series,
    coverage_hours: pd.Series,
    expected_hours: int = 168,
) -> pd.Series:
    """Calculate V1 coverage-aware empirical persistence ratio in [0, 1].

    Formula:
        persistence = problem_hours / max(coverage_hours, expected_hours)
    """
    denom = np.maximum(coverage_hours, float(expected_hours))
    return (problem_hours / denom).clip(0.0, 1.0)


def calc_bayesian_persistence(
    k_impaired: pd.Series,
    n_observed: pd.Series,
    alpha: float = 1.0,
    beta: float = 9.0,
    expected_hours: int = 168,
) -> pd.Series:
    """Calculate V2 Bayesian Beta-Binomial posterior mean with coverage shrinkage.

    Formula:
        p = (alpha + k_imp) / (alpha + beta + max(n_obs, expected_hours))
    """
    eff_n = np.maximum(n_observed, float(expected_hours))
    return (alpha + k_impaired) / (alpha + beta + eff_n)


def calc_coverage_and_silence(
    coverage_series: pd.Series,
    expected_hours: int = 168,
) -> tuple[pd.Series, pd.Series]:
    """Return observed coverage ratio in [0, 1] and silent hour count."""
    coverage_ratio = (coverage_series / float(expected_hours)).clip(0.0, 1.0)
    silent_hours = np.maximum(0, expected_hours - coverage_series)
    return coverage_ratio, silent_hours
