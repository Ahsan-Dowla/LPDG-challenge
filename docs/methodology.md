# Methodology

## Part 1 — V1 Optimized Evidence Ranker

### Objective
Rank exactly 15 gateways per Monday that have the highest expected operational
value of a site visit, using only information available before that Monday.

### Evidence Score Formula

```
score = persistence_weight * persistence_pct/100
      + silence_weight    * (silent_hours / expected_weekly_hours)
      + metric_bonus
      + meter_exposure_bonus
```

Where:

- **persistence_pct**: `problem_hours / max(coverage_hours, 168) * 100`
  Fraction of the 168-hour window where a gateway was observed impaired.
  Dividing by `max(coverage_hours, 168)` prevents gateways with only a few
  reported hours from achieving artificially high persistence scores.

- **silent_hours**: `expected_weekly_hours - coverage_hours`
  Hours with no telemetry. A silent gateway is treated as at-risk, not healthy.
  High silence combined with prior impairment is a strong visit signal.

- **metric_bonus**: Extra weight when the primary failure signal is
  `disconnection_cnt` (connection interruptions) vs `offline_duration_sec`
  (raw offline time). Disconnection events correlate more strongly with
  engineer-confirmable impairment.

- **meter_exposure_bonus**: Scaled by `log1p(n_meters_installed)`.
  Gateways serving more meters have higher economic impact of impairment.

### Key Design Choices
- Uses the 7-day (168h) look-back window ending at Monday cutoff.
- No forward-looking data. Telemetry is sliced with `ts_utc < cutoff`.
- Eligibility filter: gateways must have been installed before the week and
  not yet decommissioned.
- Scores are deterministic: given the same data snapshot, the ranking is
  identical on every run.

---

## Part 2 — V2 Probabilistic Ranker

### Objective
Produce a principled, probabilistic ranking that separates two independent
quantities: **impairment probability** and **economic exposure**, then
combines them into an expected visit value.

### Algorithm

```
P(impaired | evidence) estimated from:
  - Impairment ratio: problem_hours / expected_weekly_hours
  - Persistence: problem_hours / max(coverage_hours, 168)
  - Bayesian prior updated with per-gateway historical track record
  - Clipped to [MIN_PROB, MAX_PROB] to prevent over-confidence

Economic exposure:
  exposure = n_meters_installed * VISIT_COST_EUR * IMPAIRMENT_IMPACT_RATE

Expected value of visit:
  EV = P(impaired) * exposure - (1 - P(impaired)) * VISIT_COST_EUR

score = EV   (in euros)
```

### Key Properties
- **Bayesian**: prior on P(impaired) is informed by a gateway's long-run history.
  A gateway with 8 weeks of consecutive failures has higher credibility than
  one with a single noisy week.
- **Expected-value framing**: the score is interpretable as the estimated
  economic benefit of prioritising this gateway for a visit.
- **No ML model**: there are no trained weights, no feature matrices, and no
  cross-validation splits. V2 is purely statistical/probabilistic.
- **Deterministic**: identical inputs produce identical outputs.

### Important Caveats
- "Simulated economic value" is a modelling construct based on assumed
  cost parameters. It is NOT a realized saving.
- Field visits are historically biased outcomes (not clean supervised labels).
  V2 is calibrated against signal evidence, not against visit success rates.
- V2 is the Part 2 challenger. V1 remains the official Part 1 submission.
  Do not promote V2 as strictly superior without acknowledging its assumptions.

---

## Baseline — 3-Sigma Anomaly Ranker

Used as a statistical reference point. Ranks gateways by how many standard
deviations their offline_duration_sec exceeds the population mean.
Produces `predictions_baseline.csv` for comparison only.
