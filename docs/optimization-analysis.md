# Gateway Ranking Optimization Analysis

**Scope:** analysis only. No production code, `predictions.csv`, or `DECISIONS.md` was changed.

## Evidence and limitations

The local repository does not contain `01-Challenge-Brief.pdf` or `02-Data-Dictionary.pdf`. This report therefore uses the checked-in exploration, current `baseline_3sigma.py`, current `src/part1/` implementation, and the local telemetry, meter-read, field-visit, engineer-review, and gateway-master data. Definitions that require the missing Data Dictionary are described conservatively from column names and observed behavior.

The analysis normalizes gateway IDs, removes the 6,547 exact duplicate gateway-hour rows, and respects the Monday 00:00 UTC cutoff when discussing predictive relationships. Historical visits and engineer reviews are used as evaluation evidence, not as features that would have been available to the historical prediction.

## Key findings

| Question | Evidence-based answer |
|---|---|
| What looks genuinely problematic? | Persistent elevated offline time and disconnections, often accompanied by low meter-read success. Reboot counts help, but are rarer. “Schlecht” gateways in February had much higher telemetry than “Normal” gateways. |
| Which metrics matter? | `offline_duration_sec` and `disconnection_cnt` are the strongest baseline signals. `no_conn_importance` is a powerful corroborating composite. `reboot_cnt` is useful for a subset of hardware/firmware problems but is sparse. |
| Does deterioration precede read failure? | High telemetry levels in the preceding week are strongly associated with lower read rate in the following meter-read week. Short-term level-versus-28-day change was weak, so persistence/absolute severity is better supported than a noisy slope. This is correlation with temporal precedence, not proof of causation. |
| What makes a visit useful? | Strong, persistent telemetry plus measurable meter-read impact and high gateway business impact. Historical visits were useful only 34.7% of the time by the `Fehler behoben` outcome; 60.7% ended `Kein Fehler gefunden`. |
| How suspicious is 3-sigma? | Of 120 current selections, 83 (69.2%) had at least one independent problem indicator; 37 (30.8%) did not. This is a potential-false-positive rate, not a proven error rate, because labels and historical visits are incomplete and biased. Score bands did not clearly separate outcomes. |
| How much impact does a gateway represent? | `n_meters_installed` is the clearest available exposure measure. It ranges from 40 to 822, so equal technical severity can imply materially different customer/reading impact. |

## 1. What does a genuinely problematic gateway look like?

The strongest observed profile is **persistent connectivity degradation**, not an isolated extreme hour:

- The February engineer-review comparison covered 54 `Schlecht` and 56 `Normal` gateways with telemetry. Group means were:

| February per-gateway mean | Schlecht | Normal | Approximate contrast |
|---|---:|---:|---:|
| `offline_duration_sec` | 28,006.9 | 943.5 | 29.7x |
| `disconnection_cnt` | 5.80 | 0.33 | 17.6x |
| `reboot_cnt` | 0.21 | 0.03 | 7.0x |
| `no_conn_importance` | 1,337,477 | 3,643 | 367x |
| `reboot_importance` | 11,210 | 35 | 320x |

- Meter-read impact agrees with that picture. Across all meter-read rows, the mean read rate was 84.5%; 567 rows (7.8%) were below 50%.
- In the leakage-aware temporal join (7,206 meter-read weeks with usable prior telemetry), the prior seven-day telemetry level was strongly negatively associated with the meter-read rate in the following week: Spearman rank correlations were approximately -0.611 for offline duration, -0.500 for disconnections, and -0.410 for reboots. `no_conn_importance` was -0.600 and `reboot_importance` was -0.418.
- Meter-read rows below 90% had mean prior-week telemetry of 9,867 offline seconds, 2.84 disconnections, and 0.23 reboots, versus 129.8, 0.23, and effectively 0 for rows at or above 90%.
- Missing telemetry should remain a separate state. It may represent outage, installation timing, or decommissioning; it is not evidence of health by itself.

**Interpretation:** a genuinely problematic gateway is more likely to show repeated or sustained connectivity loss and downstream read degradation. A single large counter value without persistence or downstream impact is weaker evidence.

## 2. Which telemetry metrics actually matter?

### Strongest baseline metrics

**`offline_duration_sec`**

This is the strongest baseline discriminator in the available evidence. It has the largest Schlecht/Normal contrast and the strongest temporal association with next-week read rate. It is also highly skewed: 66,596 rows exceed 3,600 seconds and the maximum is 726,642 seconds. It should therefore be used as an anomaly/severity signal, not naively interpreted as an ordinary one-hour duration.

**`disconnection_cnt`**

This is the second strongest baseline signal. It separates engineer labels substantially and has a meaningful negative relationship with subsequent read rate. Repeated elevated disconnections are more credible than one isolated high count.

**`reboot_cnt`**

This is directionally useful but sparse: 98.4% of observed values are zero; 1,913 rows exceed 5 and 1,003 exceed 10. It should contribute as corroboration or a specific failure mode, not dominate the score.

### Additional signals

**`no_conn_importance`** is the strongest additional candidate. It has a 367x Schlecht/Normal group-mean contrast and a prior-week/read-rate correlation of approximately -0.600. It appears to encode the operational importance of connection loss and may add information beyond raw event counts, but this should be tested with ablations before production use.

**`reboot_importance`** also separates the review groups dramatically, but it is highly skewed and closely related to reboot behavior. Treat it as corroboration, not an independent full-weight signal until redundancy is measured.

**Network quality, radio, load, and uptime fields** are plausible candidates, but the existing exploration did not establish their relationship with downstream impact. They should not be added blindly. First test them against time-forward read-rate outcomes and repair-confirming visits.

### Noisy or misleading signals

- Raw `offline_duration_sec` values above 3,600 cannot be treated as literal hourly durations without clarification from the missing Data Dictionary.
- Reboot and counter fields contain sparse high values and possible saturation/rollover behavior.
- Missing telemetry cannot be scored as zero or healthy.
- Adding all 57 columns would create duplicated signals, unstable weights, and more opportunities for leakage or data-quality artifacts.

## 3. Does telemetry deterioration precede meter-read failures?

There is useful evidence of **temporal precedence**, but not causation.

For each meter-read week, telemetry from the preceding seven days was aggregated strictly before that week. The resulting prior-week levels were negatively associated with the read rate observed in that week:

| Prior-week telemetry signal | Spearman rho with following read rate |
|---|---:|
| `offline_duration_sec` | -0.611 |
| `no_conn_importance` | -0.600 |
| `disconnection_cnt` | -0.500 |
| `reboot_importance` | -0.418 |
| `reboot_cnt` | -0.410 |

The relationship is operationally large: rows below 90% read rate had 0.724 mean read rate, compared with 0.944 for rows at or above 90%. Their prior-week offline and disconnection levels were also much higher.

However, the simple change from the prior seven-day level to the preceding 28-day level was weakly associated with the next read rate, with correlations approximately -0.058 for offline duration, -0.072 for disconnections, and -0.016 for reboots. This argues against relying only on a short-term slope. A gateway can be persistently bad without a dramatic new week-over-week increase.

The engineer review is cross-sectional in February, not a future outcome label, so it supports association but not a temporal claim. Field visits also cannot cleanly establish precedence because the historical process was not randomized and the observed visit period ends before most scored weeks.

## 4. What makes a visit more or less likely to be useful?

Historical visit outcomes provide a direct warning about the cost of weak prioritization:

| Outcome | Count | Share |
|---|---:|---:|
| `Fehler behoben` | 223 | 34.7% |
| `Kein Fehler gefunden` | 390 | 60.7% |
| `Kein Zugang` | 29 | 4.5% |

Parts were recorded on only 25.9% of visits. “Useful” is therefore not identical to “part replaced”: a visit can diagnose a problem without replacing a part, and `Kein Zugang` is an execution failure rather than a false alarm.

Signals likely to increase usefulness:

- persistent high offline duration and disconnection counts;
- poor recent or repeated meter-read success;
- corroboration across independent telemetry families;
- high `n_meters_installed`, because the consequence of continued degradation is larger;
- evidence that the gateway is active and producing data, rather than an installation/decommissioning artifact.

Signals likely to decrease usefulness:

- a single isolated spike without persistence;
- high 3-sigma count caused by a gateway with an unusually quiet historical baseline;
- extreme counter values whose physical meaning is uncertain;
- low telemetry coverage treated as normal telemetry;
- repeated historical visits without repair evidence, although this is confounded by access, scheduling, and the old spreadsheet/gut-feel process.

**Important bias:** field visits were assigned by the historical process, so these outcomes are not a randomized test of gateway condition. A gateway may have been visited precisely because it already looked severe, and “no fault found” may reflect intermittent failure, access problems, or poor diagnostic timing.

## 5. How often does current 3-sigma look like a false positive?

The current Part 1 pipeline selected 120 gateway-week rows. After joining independent evidence:

- 26 rows had an engineer review of `Normal` and 22 had `Schlecht`; 72 had no review label.
- 61.7% of selected rows had a gateway-level historical mean read rate below 90%.
- No selected row had a gateway-level historical mean read rate below 50%, although some had substantial sub-50% week frequency.
- 69.2% had at least one of: mean read rate below 90%, `Schlecht` review, or at least one repaired historical visit.
- 30.8% lacked those indicators. These are **potential false positives**, not proven false positives.

The score itself did not provide much separation:

| Score band | Rows | Mean historical read rate | Below 90% | Schlecht share | Repaired visits | No-fault visits |
|---|---:|---:|---:|---:|---:|---:|
| 6-20 | 54 | 0.831 | 61.1% | 14.8% | 49 | 63 |
| 21+ | 66 | 0.859 | 62.1% | 21.2% | 67 | 67 |

This shows why “more anomaly hours” is not yet equivalent to “more operational value.” The highest-scoring examples with little independent evidence included:

| Week | Gateway | Score | Historical mean read rate | Recent offline mean | Comment |
|---|---|---:|---:|---:|---|
| 2026-02-23 | `0228A99EE35A` | 39 | 0.929 | 14,259 sec | Severe telemetry anomaly but no review/read-rate failure evidence in the available join |
| 2026-02-23 | `06238EE3BE6C` | 38 | 0.928 | 6,024 sec | High anomaly score and prior visits, but no repair/review evidence in this comparison |
| 2026-02-16 | `0A4673793B3E` | 38 | 0.961 | 585 sec | High score despite relatively strong historical read rate |

Conversely, lower-ranked selections still had strong evidence, for example `06787526FEB3` with score 16, mean read rate 0.769, 11.5% of weeks below 50%, `Schlecht` review, and two historical visits. This is a potential false negative within the ordering, not a missed gateway outside the Top-15.

The current method also has a structural limitation: it ranks only gateways that have telemetry in the recent window. It does not model telemetry coverage as a risk signal and does not use meter impact.

## 6. Business impact per gateway

The available direct exposure measure is `n_meters_installed`:

- range: 40 to 822 meters;
- mean: approximately 189 meters;
- the challenge data contains 332 master records, including 12 decommissioned gateways.

The current baseline selections average 205.6 installed meters per selected gateway (median 170), versus 189.0 across the master table. The selected Top-15 expose approximately 2,683 to 3,572 installed meters per week across the eight scored weeks. Only three selected gateway-week rows overlap a visit within the following seven days, and all three historical outcomes were `Fehler behoben`; this is too small and too operationally confounded to estimate visit success, but it confirms that same-week historical outcome matching is not a sufficient evaluation design.

A gateway affecting 822 meters can represent more than 20 times the installed-meter exposure of one affecting 40 meters. If technical severity is similar, prioritizing the larger gateway is operationally defensible because each additional week of poor service can affect more customer readings.

A practical impact measure should combine exposure with observed degradation, rather than simply ranking by meter count:

```text
impact = n_meters_installed
         * estimated_fraction_of_meters_at_risk
         * persistence_factor
```

The simplest defensible first approximation is:

```text
impact = n_meters_installed * (1 - recent_read_rate)
```

When recent read rate is unavailable, use a bounded telemetry-severity proxy and label the estimate as uncertain. Do not multiply raw offline seconds by meter count until the duration semantics are clarified.

## 7. Optimization recommendation, without implementation

### A. Current baseline logic

For each Monday, the current logic uses the preceding 28 days to calculate gateway-specific mean and standard deviation for `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`. It flags the preceding seven days when a value exceeds its own mean by more than three standard deviations, counts flagged metric-hours, sorts descending by count, and selects 15.

The current Part 1 wrapper additionally normalizes IDs, removes exact duplicates, excludes gateways not active at the cutoff, and applies deterministic gateway-ID tie-breaking.

### B. Problems and limitations

1. It optimizes anomaly count, not expected operational value.
2. It does not use meter exposure or meter-read impact.
3. It treats three metrics as additive evidence even when they may be correlated.
4. A gateway-specific mean/std baseline can make a quiet gateway rank highly after a small absolute spike.
5. It has no explicit persistence or coverage quality factor.
6. It does not distinguish a repair-confirming outcome from a no-fault visit during ranking.
7. Historical labels and visits are incomplete and biased.
8. Extreme counter semantics and missing telemetry remain data-quality risks.

### C. Strongest signals found

- recent/persistent `offline_duration_sec`;
- recent/persistent `disconnection_cnt`;
- `no_conn_importance` as a candidate corroborating signal;
- repeated poor meter-read rate;
- `n_meters_installed` as business exposure;
- corroboration across telemetry and meter-read families.

### D. Signals that should not be used blindly

- every available telemetry column;
- raw sums of `offline_duration_sec`;
- a short-term deterioration delta alone;
- engineer review as a universal label, because it covers only 120 gateways and one reviewer;
- historical field-visit outcome as unbiased ground truth;
- missing telemetry interpreted as healthy;
- future meter-read, visit, or review data in a historical decision.

### E. Proposed ranking factors

Use a small, interpretable score with separate components:

1. **Persistent technical severity:** robustly normalized recent offline duration and disconnection behavior.
2. **Corroboration:** `reboot_cnt` and `no_conn_importance` only when they add information beyond the first two components.
3. **Downstream impact:** recent meter-read failure rate and number of affected meters.
4. **Persistence:** repeated bad weeks or bad hours, not only one spike.
5. **Coverage state:** distinguish active gateway gaps from not-yet-installed/decommissioned gateways.
6. **Business exposure:** installed meters, bounded so it cannot overwhelm technical evidence.

### F. Proposed scoring formula/pseudocode

This is a proposal for the next experiment, not an implementation:

```text
for each eligible gateway and Monday cutoff:
    technical = robust_score(offline_duration_sec, disconnection_cnt)
    corroboration = incremental_score(reboot_cnt, no_conn_importance)
    persistence = fraction_of_recent_days_or_weeks_with_bad_signal
    read_failure = clip(1 - recent_meter_read_rate, 0, 1)
    exposure = log1p(n_meters_installed) / log1p(network_max_meters)

    evidence = technical + corroboration + persistence
    impact = read_failure * exposure

    expected_value_score = P(useful_visit | evidence, impact) * 600 * persistence
                         - P(wasted_visit | evidence) * 380
```

Initially, estimate the probabilities with transparent historical bins or out-of-time cross-validation rather than a complex model. Keep the technical and impact components visible in the reason field and audit logs.

### G. Cost-sensitive prioritization

The direct decision rule is:

```text
prioritize when expected avoided unattended-failure cost
    > expected wasted-visit cost
```

A useful visit has value because it can avoid another week of a broken gateway. The €600 unattended-failure cost is recurring, so persistence should increase priority. The €380 wasted-visit cost means weak, isolated anomalies should be penalized. The exact probability estimates must be learned from time-forward historical evaluation; they should not be invented from the raw costs alone.

### H. Selecting exactly 15 gateways

At each Monday cutoff:

1. build the eligible active-gateway universe;
2. compute the score using only data before the cutoff;
3. sort by expected value descending, then canonical gateway ID ascending;
4. select exactly the first 15;
5. emit rank 1 through 15, with an operational reason and a coverage/uncertainty indicator.

### I. Evaluation plan

Use rolling, time-forward backtesting:

- freeze each historical cutoff;
- compute features using only earlier data;
- evaluate next-week meter-read degradation and subsequent repair-confirming visits;
- compare current 3-sigma against the proposed score at Top-15, Top-30, and full-ranking levels;
- report precision for poor-read outcomes, repair-confirming visit rate, avoided-cost proxy, calibration, and stability;
- include an ablation table for each added signal;
- bootstrap or provide confidence intervals because the number of engineer reviews is small.

The primary metric should be expected operational value, not anomaly count:

```text
600 * confirmed_bad_or_persistently_failed gateways captured
- 380 * apparently unnecessary visits
```

This is a proxy until a reliable visit-success label is defined.

### J. Risks, assumptions, and limitations

- The missing PDFs prevent verification of their exact definitions and cost wording.
- Engineer reviews are cross-sectional, balanced 60/60, and written by one reviewer.
- Historical visits are selected by an old process and are not randomized.
- `Kein Fehler gefunden` may include intermittent failures or diagnostic timing errors.
- Meter-read records are weekly and may lag telemetry or reflect external causes.
- `offline_duration_sec` has physically implausible values for an hourly duration.
- Read-rate joins are not available for every gateway-week.
- No analysis here establishes causation.
- Recommendations should remain frozen until time-forward evaluation demonstrates improvement over the accepted baseline.

## Decision Summary

1. **What does a genuinely problematic gateway look like?**  A gateway with persistent high offline duration and disconnection activity, corroborated by poor meter-read success and, where available, engineer `Schlecht` evidence. Reboots strengthen the case but are not required.

2. **Which telemetry metrics actually matter?**  `offline_duration_sec` and `disconnection_cnt` matter most in the observed data. `no_conn_importance` is a strong additional candidate. `reboot_cnt` is useful but sparse. Extreme raw values, missingness, and untested columns require careful treatment.

3. **Does telemetry deterioration precede meter-read failures?**  Prior-week telemetry levels precede and strongly correlate with following-week read-rate degradation. The evidence supports temporal precedence, not causation. Persistent level is better supported than a simple one-week deterioration delta.

4. **What makes a field visit likely to be useful?**  Persistent multi-signal technical severity, downstream read impact, and high meter exposure. Historical evidence shows substantial waste: 60.7% of visits ended with no fault found, though selection bias prevents treating that as a clean false-positive rate.

5. **Where does current 3-sigma appear to produce potential false positives/negatives?**  37 of 120 selected rows lacked the independent evidence used here and are potential false positives. High scores did not clearly outperform low scores. Some low-ranked selected gateways had poor read rates, `Schlecht` reviews, or repairs, indicating ordering weaknesses and potential false negatives within the Top-15.

6. **What business-impact measure should influence Top-15 ranking?**  Use installed meters multiplied by a bounded estimate of affected fraction, initially `n_meters_installed * (1 - recent_read_rate)`, with telemetry severity and persistence required as evidence. A high-exposure gateway should outrank a low-exposure gateway at similar technical severity.

---

## 8. Phase 2: Probabilistic & Expected-Value Ranking V2 Evaluation

### 8.1 Model Formulation & Architecture

Implemented in `src/part1/ranker_v2.py` and wrapped by `src/services/v2_ranker.py`:
1. **Robust Scaling**: Replaces Gaussian $\mu \pm 3\sigma$ with Median Absolute Deviation (MAD) scaled positive deviations:
   $$z_{\text{pos}} = \max\left(0, \frac{x - \text{median}(x)}{1.4826 \cdot \text{MAD}(x) + \epsilon}\right), \quad S_{\text{metric}} = \frac{z_{\text{pos}}}{\max(z_{\text{pos}})}$$
   Applied to `offline_duration_sec`, `disconnection_cnt`, `no_conn_importance`, and `reboot_cnt`.
2. **Bayesian Beta-Binomial Persistence**: Models hourly failure rate with prior $\text{Beta}(\alpha=1.0, \beta=9.0)$ and $168\text{ h}$ effective weekly sample size:
   $$p_{\text{persistence}} = \frac{\alpha + k_{\text{imp}}}{\alpha + \beta + \max(n_{\text{obs}}, 168)}$$
   Eliminates low-coverage persistence inflation (e.g. 5/5h impaired yields $p=0.33$, not $1.0$).
3. **Calibrated Impairment Probability**:
   $$P(\text{impaired} \mid \text{evidence}) = \text{clip}\left(\frac{S_{\text{tech}} + 0.30 \cdot p_{\text{persistence}} + 0.15 \cdot S_{\text{no\_conn}}}{\max(\text{evidence})}, 0.01, 0.99\right)$$
4. **Economic Decision Score (€ Expected Value)**:
   $$\mathbb{E}[\text{Value of Visit}] = P(\text{impaired}) \cdot [€600 \cdot (1 + 0.3 \cdot \text{exposure})] - [1 - P(\text{impaired})] \cdot €380$$

### 8.2 Historical 22-Week Time-Forward Backtest (330 Site Visits)

Simulated strictly forward in time across 22 historical weeks (2025-09-01 to 2026-01-26) where following-week ground-truth meter reading outcomes are observed:

| Metric | Optimization V1 | Probabilistic V2 | Delta (V2 vs V1) | Operational Significance |
|---|---|---|---|---|
| **Mean Following Read Rate** | 0.4583 | **0.4104** | -0.0479 | V2 targets more severely degraded sites |
| **Precision@15 (Read < 80%)** | 84.8% (280/330) | **92.1% (304/330)** | **+7.3%** | **24 additional failing gateways rescued** |
| **Precision@15 (Read < 50%, Blackout)** | 57.0% (188/330) | **64.5% (213/330)** | **+7.5%** | **25 additional blackout sites resolved** |
| **Wasted Visits (Read $\ge 80\%$)** | 50 / 330 (15.2%) | **26 / 330 (7.9%)** | **-48.0%** | **Wasted technician visits cut in half (-24)** |
| **Net Economic Payoff (€)** | €149,000 | **€172,520** | **+€23,520** | **+15.8% financial return on field visits** |
| **Brier Score** | N/A (uncalibrated) | **0.0838** | — | Strong probabilistic calibration |
| **Unique Fleet Coverage** | 71 gateways | 71 gateways | 0 | Preserves broad geographic network coverage |

### 8.3 8 Scored Weeks Benchmark (Engineer Review Ground Truth)

| Strategy | Confirmed Bad (`Schlecht`) | False Alarm (`Normal`) | Unreviewed | S/N Ratio | Read Rate < 80% |
|---|---|---|---|---|---|
| **Baseline 3-Sigma** | 22 | 26 | 72 | 0.85 | 24 / 120 |
| **Optimization V1** | **89** | **6** | 25 | **14.83** | 83 / 120 |
| **Probabilistic V2** | **89** | **6** | 25 | **14.83** | **88 / 120 (+5)** |

### 8.4 Concrete Failure Case Investigation

1. **Gateways V1 Selected but V2 Rejected (47 instances)**:
   - Mean next read rate: **0.6959**; **53.2% were false alarms** (read rate $\ge 80\%$).
   - *Why V1 was wrong*: V1's min-max scaling allowed moderate disconnection spikes on low-exposure gateways to crowd out severe blackouts. V2's robust positive z-scores and expected-value decision model correctly rejected these weak candidates (e.g. `0ED5057ECE3F` with read rate 87.4%).
2. **Gateways V2 Selected but V1 Rejected (47 instances)**:
   - Mean next read rate: **0.3597**; **97.9% were confirmed true failures** (read rate $< 80\%$).
   - *Why V2 succeeded*: V2 detected sustained silence and high persistence (e.g. `06787526FEB3`, `023ADDDECF84` with 100% impaired hours and severe blackout outcomes).
3. **V2 False Alarms (26 instances, Read $\ge 80\%$)**:
   - E.g. `02892F51E1CB`, `06B641B75B29`.
   - *Why the model was wrong*: High disconnection counts and packet loss occurred, but attached meters retained interval readings in local non-volatile memory and backfilled data during intermittent online windows.
