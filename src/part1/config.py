from __future__ import annotations

import datetime as dt

METRICS = ["offline_duration_sec", "disconnection_cnt", "reboot_cnt"]
# Additional telemetry columns used by the optimized ranker
EXTRA_TELEMETRY_COLS = ["no_conn_importance"]

SCORED_WEEKS = [dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)]
VISITS_PER_WEEK = 15
BASELINE_DAYS = 28
RECENT_DAYS = 7
EXPECTED_WEEKLY_HOURS = 168
SIGMA = 3.0
OUTPUT_COLUMNS = ["week_start", "rank", "gateway_id", "score", "reason"]

# Optimized ranker weights (see DECISIONS.md for rationale)
OPT_W_OFFLINE = 0.6       # weight of offline_duration in technical score
OPT_W_DISC = 0.4          # weight of disconnection_cnt in technical score
OPT_W_PERSISTENCE = 0.3   # additive persistence term
OPT_W_CORROBORATION = 0.2 # additive no_conn_importance corroboration
OPT_W_EXPOSURE = 0.3      # exposure multiplier weight (0 → no exposure effect)

# Available strategy names
STRATEGY_BASELINE = "baseline"
STRATEGY_OPTIMIZED = "optimized"
STRATEGY_V2 = "v2"
DEFAULT_STRATEGY = STRATEGY_OPTIMIZED

# V2 Probabilistic Ranker Parameters
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
