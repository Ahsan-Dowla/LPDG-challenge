# Part 1 Decisions

## 1. What needs a visit?

A gateway needs a visit when recent operational telemetry provides enough evidence of abnormal behaviour that it should receive one of the 15 limited weekly visits. This is a ranking decision, not a claim that failure is certain.

## 2. Detection versus prediction

Part 1 prioritises recent anomalies. For each gateway, the ranker compares the most recent seven days with that gateway's own trailing 28-day baseline using the supplied 3-sigma method. This is intentionally a detection baseline; it does not pretend to have a future-failure label.

## 3. Temporal boundary

Every scored week is evaluated at Monday 00:00 UTC. Telemetry rows with timestamps on or after that boundary are excluded. The same cutoff rule is used for service eligibility: a gateway installed after the cutoff or decommissioned on or before it cannot be selected.

## 4. Duplicate telemetry

Exact duplicate `(gateway_id, timestamp)` rows are removed before feature generation, keeping the first row. The exploration found value-for-value duplicates, so aggregation would otherwise over-count an hour without adding information.

## 5. Gateway IDs

All data-source IDs are converted to stripped, uppercase, compact hexadecimal IDs by removing colons before joins or ranking. This makes compact and MAC-style representations equivalent.

## 6. Missing telemetry

Missing telemetry is not silently treated as healthy. The candidate set is first restricted to gateways active at the cutoff, then the ranker reports observed recent coverage in each reason. Gateways with no usable historical telemetry cannot be scored by this baseline and are rejected rather than assigned an invented healthy score.

## 7. Extreme counters

The accepted baseline uses `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt` without arbitrary physical caps. Values are compared against each gateway's own distribution, preserving the supplied challenge logic while making the choice explicit.

## 8. Score and ties

`score` is the number of metric-hours exceeding the gateway-specific 3-sigma threshold in the recent seven-day window. Higher is more urgent evidence. Equal scores are ordered by canonical `gateway_id` ascending so repeated runs are identical.

## 9. Part 2 focus

**Part 2 focus: DevOps.** Software-development practices are the foundation; the deeper specialization is operational reliability, reproducibility, CI/CD, containerisation, health checks, logging, configuration, and debugging.
