"""Centralized settings and domain constants for LPDG Gateway Prioritization."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

# Paths & Environment Variables
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data")).resolve()
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT_DIR / "outputs")).resolve()
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Telemetry metrics
METRICS = ["offline_duration_sec", "disconnection_cnt", "reboot_cnt"]
EXTRA_TELEMETRY_COLS = ["no_conn_importance"]

# Evaluation window constants
SCORED_WEEKS = [dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)]
VISITS_PER_WEEK = 15
BASELINE_DAYS = 28
RECENT_DAYS = 7
EXPECTED_WEEKLY_HOURS = 168
SIGMA = 3.0
OUTPUT_COLUMNS = ["week_start", "rank", "gateway_id", "score", "reason"]

# Strategy Identifiers
STRATEGY_BASELINE = "baseline"
STRATEGY_V1 = "v1"
STRATEGY_OPTIMIZED = "optimized"  # Alias for V1
STRATEGY_V2 = "v2"

# Default Strategy is V1 (Frozen Part 1 official strategy)
DEFAULT_STRATEGY = os.getenv("RANKING_STRATEGY", STRATEGY_V1).lower()

# Optimization V1 Weights (Frozen Part 1 Parameters)
OPT_W_OFFLINE = 0.6
OPT_W_DISC = 0.4
OPT_W_PERSISTENCE = 0.3
OPT_W_CORROBORATION = 0.2
OPT_W_EXPOSURE = 0.3

# Probabilistic V2 Parameters (Expected Value & Decision Model)
V2_PRIOR_ALPHA = 1.0
V2_PRIOR_BETA = 9.0
V2_COST_WASTED_VISIT = 380.0
V2_COST_UNATTENDED_FAILURE = 600.0
V2_W_EXPOSURE = 0.3
V2_W_OFFLINE = 0.55
V2_W_DISC = 0.35
V2_W_CONN = 0.10
V2_W_PERSISTENCE = 0.30
V2_W_CORROBORATION = 0.15
