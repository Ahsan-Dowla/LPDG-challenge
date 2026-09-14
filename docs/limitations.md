# Known Limitations

This document describes the principal limitations, failure modes, and design
constraints of the LPDG gateway ranking system. Awareness of these limitations
is as important as the algorithm's strengths.

---

## 1. Biased Historical Labels

Field visit outcomes (engineer reviews, meter read success rates) are
**observationally biased**. A gateway only receives a visit if it was
highly ranked in the first place. Gateways that were never visited cannot
be labelled "healthy confirmed" — they are simply unobserved.

**Consequence**: Any evaluation that uses field visit outcomes to compare
strategies should be treated as a directional signal, not a ground truth.
Hit-rate metrics computed this way are biased upward for all strategies.

---

## 2. Silent Gateway Ambiguity

A gateway that sends no telemetry for several days is treated as silent
(high-risk). In practice, silence can mean:

- Hardware failure or prolonged disconnection (true impairment)
- Successful decommission not yet reflected in gateway master
- Network partition only affecting telemetry upload (gateway is functional)
- Routine maintenance window

The ranking heuristic assumes silence is correlated with impairment,
which is the conservative/safe assumption for visit prioritisation.

---

## 3. V2 Economic Parameters Are Assumed

The V2 expected-value score uses assumed cost constants
(`VISIT_COST_EUR`, `IMPAIRMENT_IMPACT_RATE`). These are calibration
parameters, not empirically validated costs.

**The €172,520 simulated economic value is a modelling estimate, not
a realised saving.** It represents the potential value if all V2 assumptions
held exactly.

---

## 4. No True Supervised Labels

Neither V1 nor V2 was trained or calibrated on labelled examples of
"impaired vs healthy" gateways verified by engineers. Both algorithms
are purely evidence-based (V1) or probabilistic (V2), without a
labelled training set.

---

## 5. 168-Hour Look-Back Window Is Fixed

Both strategies use a fixed 7-day look-back ending at the Monday cutoff.
A gateway that was severely impaired 10 days ago but healthy last week
receives no credit for the older event. Conversely, a gateway with a
one-day failure spike near the cutoff may be over-prioritised.

Longer windows were not evaluated due to the challenge's 8-week scope.

---

## 6. Coverage Normalisation Assumption

Persistence is computed as `problem_hours / max(coverage_hours, 168)`.
This treats a gateway with only 20 hours of reported telemetry the same
as one that is known healthy for 148 hours and failing for 20. The
normalisation is conservative (avoids inflating sparse reporters) but
may underrank gateways that genuinely have poor telemetry collection.

---

## 7. V1 and V2 Were Evaluated Over Only 8 Weeks

Both strategies were evaluated over exactly 8 consecutive weeks in a
single Q1-2026 period. This is insufficient to draw statistically
significant conclusions about which strategy is superior. The engineer
review totals (V1: 89, V2: 89 confirmed visits) are identical and within
normal sampling variation for 120 ranked slots.

---

## 8. API Is Not Production-Hardened

The FastAPI service (`src/api/`) is a reference implementation for
demonstrating the ranking pipeline programmatically. It lacks:

- Authentication / API key management
- Rate limiting
- Persistent database backend
- Async data refresh (it loads data on startup)
- Production-grade error recovery

---

## 9. Docker Image Contains No Data

The `Dockerfile` and `docker-compose.yml` mount `./data` as a read-only
volume. The image itself does not bundle any gateway or telemetry data.
Deploying the image without mounting the data directory will result in
a startup failure.
