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

The codebase preserves the exact baseline algorithm under `--strategy baseline`. The CLI defaults to V1 (--strategy v1), with optimized retained as a backward-compatible alias. Both modes pass all schema and validation rules verified by `validate_submission.py`.

## 12. Phase 1 Software Architecture & API Decoupling

The Web API layer (`src/api`) is strictly decoupled from the ranking formula. The API interacts solely with the service layer (`RankingService`), which depends on an abstract `BaseRanker` protocol. The current Optimization V1 implementation is wrapped in `V1OptimizedRanker` and plugged into this abstraction without modifying the frozen Part 1 algorithm. This design guarantees:
1. Swappability: Future Part 2 probabilistic models can be introduced with zero changes to API routes or error handling.
2. Stability: The existing CLI (`main.py`) and validator (`validate_submission.py`) continue to run directly against the Part 1 pipeline with 100% backward compatibility.
3. Information Hiding: Internal server details, stack traces, and filesystem paths are never leaked to API callers.

## 13. Phase 2 Probabilistic & Expected-Value Ranking V2

In Phase 2, we built **Gateway Ranking V2 (`src/part1/ranker_v2.py`)** evaluated as an operational decision system rather than an uncalibrated classifier:

### 1. Robust Anomaly Scaling
Gaussian $\mu \pm 3\sigma$ assumes normal distributions and breaks down when telemetry has heavy tails and extreme spikes (e.g. `offline_duration_sec` std of 1.2M vs median 0). V2 computes median absolute deviation (MAD) normalized robust $z$-scores:
$$z = \frac{x - \text{median}}{1.4826 \cdot \text{MAD} + \epsilon}, \quad z_{\text{pos}} = \max(0, z)$$
Only positive excess is treated as anomalous and normalized by active network maximum, yielding robust separation between healthy and degraded equipment.

### 2. Bayesian Beta-Binomial Persistence & Silence Shrinkage
Rather than computing raw ratio of problem hours over observed hours (which rewards gateways with sparse data, e.g. 5/5h = 100%), V2 uses a Bayesian Beta-Binomial posterior with prior $\text{Beta}(\alpha=1.0, \beta=9.0)$ and effective weekly sample size ($168\text{ h}$):
$$p_{\text{persistence}} = \frac{\alpha + k_{\text{imp}}}{\alpha + \beta + \max(n_{\text{obs}}, 168)}$$
Low-coverage gateways shrink heavily toward the healthy prior (e.g. 5/5h yields $p=0.33$, not $1.0$).

### 3. Business Economics & Expected Value Decision Score
The ranking score is directly formulated in expected financial value (€ saved by visiting):
$$\mathbb{E}[\text{Value of Visit}] = P(\text{impaired}) \cdot [€600 \cdot (1 + 0.3 \cdot \text{exposure})] - [1 - P(\text{impaired})] \cdot €380$$
Where €380 is the wasted visit cost, €600 is the unattended weekly failure cost, and exposure accounts for customer meter count.

### 4. 22-Week Historical Time-Forward Backtest Evidence
Across all 22 historical weeks (330 visits evaluated against following-week ground-truth meter reads):
- **Precision@15 (Read < 80%)**: lifted from **84.8%** (V1) to **92.1%** (V2), capturing **24 additional severely degraded gateways** (304 vs 280).
- **Precision@15 (Read < 50%, Blackouts)**: lifted from **57.0%** (V1) to **64.5%** (V2), capturing **25 additional blackout sites** (213 vs 188).
- **Wasted Visits**: cut nearly in half from **50** down to **26** (wasted visit rate down from 15.2% to 7.9%).
- **Net Economic Payoff**: increased by **+€23,520** (+15.8% payoff: €172,520 vs €149,000).
- **Brier Score**: well-calibrated at **0.0838**.
- **Scored Weeks**: maintains parity on confirmed bad gateways (89 Schlecht, 6 Normal, S/N = 14.83) while increasing visits with read rate $< 80\%$ from 83 to 88.


## 14. V1 is the Official Part 1 Submission

V1 (Optimized Evidence Ranker) is the officially submitted Part 1 answer.
V2 is retained as an explicit, available challenger strategy.

Reasons for not promoting V2 as the default:
- The official 8-week evaluation showed V1 and V2 had identical engineer-confirmed
  visit counts (89 Schlecht each, 6 vs 6 Normal). There was no measurable
  operational difference in the evaluation window.
- V2's backtest improvement (+EUR 23,520 simulated economic value) is a
  *retrospective estimate on historical data* using assumed cost parameters
  (EUR 380 wasted visit, EUR 600 unattended failure). These parameters were
  not empirically derived.
- The 8-week evaluation window is statistically too short to confidently
  distinguish strategy superiority.
- V1 is simpler, more interpretable, and its assumptions are more transparent.

## 15. V2 is Retained as a Challenger

V2 remains available via `--strategy v2` and `predictions_v2.csv` for:
- Demonstrating probabilistic/expected-value decision framing.
- Historical backtest analysis (22-week walk-forward evaluation).
- Future evaluation if a longer operational window becomes available.

V2 must not be described as superior to V1 based solely on backtest evidence.
Both strategies are evaluated against biased labels (field visits can only
confirm gateways that were already ranked highly), which limits the
statistical validity of comparison.

## 16. Economic Value Estimates are Simulated

All references to "EUR savings" or "economic value" in V2 analysis are
*simulated backtest estimates* based on assumed cost parameters.
They are not realized operational savings. Documentation must reflect this.

## 17. Backtest Evidence Interpretation

The 22-week historical backtest evidence (Precision@15, Brier Score,
wasted visit counts) should be understood as:
- Computed on the same data used to inform the V2 formula design.
  No strict holdout set was used.
- Dependent on the field-visit ground truth, which is itself biased
  (gateways can only be confirmed by visiting them).
- Useful as directional signal, not as a guarantee of production performance.
