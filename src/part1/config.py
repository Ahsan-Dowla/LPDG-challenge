from __future__ import annotations

import datetime as dt

METRICS = ["offline_duration_sec", "disconnection_cnt", "reboot_cnt"]
SCORED_WEEKS = [dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)]
VISITS_PER_WEEK = 15
BASELINE_DAYS = 28
RECENT_DAYS = 7
SIGMA = 3.0
OUTPUT_COLUMNS = ["week_start", "rank", "gateway_id", "score", "reason"]
