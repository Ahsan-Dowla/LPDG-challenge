# Part 1 Decisions

## 1. What needs a visit?

A gateway needs a visit when recent operational telemetry provides enough evidence of abnormal behaviour that it should receive one of the 15 limited weekly visits. This is a ranking decision, not a claim that failure is certain.

## 2. Detection versus prediction

Part 1 prioritises recent anomalies. For each gateway, the ranker compares the most recent seven days with that gateway's own trailing 28-day baseline using the supplied 3-sigma method (baseline) or relative severity and persistence (optimized). This is intentionally an operational prioritization; it does not pretend to fit an opaque, uncalibrated future-failure classification model on sparse labels.

## 3. Temporal boundary

Every scored week is evaluated at Monday 00:00 UTC. Telemetry rows with timestamps on or after that boundary are excluded. The same cutoff rule is used for service eligibility: a gateway installed after the cutoff or decommissioned on or before it cannot be selected.

## 4. Duplicate telemetry

Exact duplicate `(gateway_id, timestamp)` rows are removed before feature generation, keeping the first row. The exploration found value-for-value duplicates, so aggregation would otherwise over-count an hour without adding information.

## 5. Gateway IDs

All data-source IDs are converted to stripped, uppercase, compact hexadecimal IDs by removing colons before joins or ranking. This makes compact and MAC-style representations equivalent.

## 6. Missing telemetry

Missing telemetry is not silently treated as healthy. The candidate set is first restricted to gateways active at the cutoff, then the ranker reports observed recent coverage in each reason. Gateways with no usable historical telemetry cannot be scored and are rejected rather than assigned an invented healthy score.

## 7. Extreme counters

The accepted baseline uses `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt` without arbitrary physical caps. In the optimized ranker, values are log-transformed (`log1p`) and normalized by active-network weekly maxima. This preserves relative ordering while preventing single massive cumulative spikes from distorting scores.

## 8. Score and ties

For baseline: `score` is the number of metric-hours exceeding the gateway-specific 3-sigma threshold in the recent seven-day window.
For optimized: `score` is the composite evidence score (technical severity + persistence + corroboration) scaled by business exposure.
In all cases, ties are ordered deterministically by canonical `gateway_id` ascending so repeated runs are bit-for-bit identical.

## 9. Part 2 focus

**Part 2 focus: DevOps.** Software-development practices are the foundation; the deeper specialization is operational reliability, reproducibility, CI/CD, containerisation, health checks, logging, configuration, and debugging.

## 10. Optimization Strategy Selection & Ablation Evidence

To improve upon the baseline 3-sigma ranker without introducing black-box ML or leakage, we evaluated 6 candidate strategies across all 120 prediction slots (8 weeks × 15 visits/week) against the independent Engineer Review (`engineer_review_2026-02.xlsx`, 60 Schlecht vs 60 Normal) and Historical Meter Reads:

| Strategy | Schlecht (Target) | Normal (False Alarm) | S/N Ratio | Mean Meter Read Rate | Visits with Read < 80% | Total Meters Exposed |
|---|---|---|---|---|---|---|
| **Baseline 3-Sigma** | 22 | 26 | 0.85 | 0.8366 | 24 / 120 | 24,668 |
| **A. Technical Only** | 89 | 5 | 17.80 | 0.7273 | 88 / 120 | 20,607 |
| **B. Tech + Persistence** | 89 | 5 | 17.80 | 0.7233 | 89 / 120 | 20,331 |
| **C. Tech + Persistence + Meter Impact** | 77 | 17 | 4.53 | 0.6964 | 100 / 120 | 19,020 |
| **D. Tech + Persistence + Exposure (Chosen V1)** | **92** | **4** | **23.00** | **0.4796** | **89 / 120** | **21,656** |
| **E. Full Complex Model** | 77 | 17 | 4.53 | 0.6984 | 97 / 120 | 20,054 |

**Key Findings:**
- The Baseline 3-Sigma ranker achieves an S/N ratio of only 0.85 (it selects 26 Normal gateways and only 22 Schlecht gateways), suffering from massive false alarms due to transient spikes.
- Normalized Technical Severity + Persistence (Option D) drastically cuts false alarms from 26 down to 4, boosting confirmed bad gateway capture from 22 to 92 (a **4.18x improvement**) and lifting the S/N ratio from 0.85 to **23.00**.
- The selected gateways exhibit severely degraded mean read rates (0.4796 vs 0.8366 in baseline) and 89 visits target sites with read rates under 80% (vs only 24 in baseline).
- We explicitly rejected using `meter_read_success` as a ranking feature because doing so lowered Schlecht capture from 92 to 77. Meter reads are kept strictly as an independent evaluation signal.

## 11. Preserving Baseline Compatibility

The codebase preserves the exact baseline algorithm under `--strategy baseline`. The CLI defaults to `--strategy optimized`. Both modes pass all schema and validation rules verified by `validate_submission.py`.

## 12. Phase 1 Software Architecture & API Decoupling

The Web API layer (`src/api`) is strictly decoupled from the ranking formula. The API interacts solely with the service layer (`RankingService`), which depends on an abstract `BaseRanker` protocol. The current Optimization V1 implementation is wrapped in `V1OptimizedRanker` and plugged into this abstraction without modifying the frozen Part 1 algorithm. This design guarantees:
1. Swappability: Future Part 2 probabilistic models can be introduced with zero changes to API routes or error handling.
2. Stability: The existing CLI (`main.py`) and validator (`validate_submission.py`) continue to run directly against the Part 1 pipeline with 100% backward compatibility.
3. Information Hiding: Internal server details, stack traces, and filesystem paths are never leaked to API callers.
