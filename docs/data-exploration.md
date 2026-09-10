# Data Exploration Report
### LPDG Innovation Hub Selection Challenge – Chunk 1

> **Date:** 2026-09-02  
> **Status:** Exploration complete; no model built, no predictions generated.

---

## 1. Dataset Overview

| Dataset | Rows | Key columns | Notes |
|---|---|---|---|
| `telemetry/` (parquet, 8 partitions) | 1,433,387 | 56 columns incl. `gateway_id`, `ts_utc`, health/reliability metrics | 2025-08 to 2026-03-31 |
| `telemetry_sample_2025-08.csv` | 181,484 | Same schema | Aug 2025 only; 280 unique gateways |
| `gateway_master.csv` | 332 | `gateway_id`, `tenant`, `site_type`, `region`, `hw_model`, `antenna_type`, `fw_version`, …, `n_meters_installed` | cp1252 encoding (German text) |
| `meter_read_success.csv` | 7,226 | `week_start`, `gateway_id`, `meters_expected`, `meters_read` | 299 gateways × 26 weeks |
| `field_visits.csv` | 642 | `visit_id`, `gateway_id`, `requested_on`, `visited_on`, `reason_reported`, `outcome`, `parts_replaced`, `technician_hours` | 247 unique gateways visited |
| `engineer_review_2026-02.xlsx` | 120 | `gateway_id`, `standort`, `Kategorie` (Normal/Schlecht), `reviewed_on`, `reviewer`, `Bemerkung` | Exactly 60 Schlecht, 60 Normal; single reviewer |

---

## 2. Data-Quality Findings

### 2.1 Gateway ID Format Inconsistency ⚠️

> **FACT:** Different datasets use different gateway ID formats.

- `telemetry` and `meter_read_success`: compact uppercase hex, e.g. `0202CB0A6B1F`
- `gateway_master`, `field_visits`, `engineer_review`: colon-separated MAC, e.g. `02:02:CB:0A:6B:1F`

All IDs can be normalized by removing colons and uppercasing. After normalization, all cross-dataset joins are clean — **no orphan IDs in meter_read or field_visits** relative to `gateway_master`.

**Action required:** Any pipeline joining these datasets must normalize IDs first.

---

### 2.2 Telemetry Duplicate Rows ⚠️

> **FACT:** 6,547 rows are exact duplicates of another row on the same `(gateway_id, ts_utc)` pair.

- **All** duplicates are exact value-for-value copies (no conflicting values).
- **All** duplicates are within the same monthly partition — not cross-partition duplicates.
- **Interpretation:** Likely an ETL/ingestion artifact where some hourly windows were written twice.

**Action required:** Deduplicate with `drop_duplicates(['gateway_id', 'ts_utc'], keep='first')` before any analysis or modelling.

---

### 2.3 `offline_duration_sec` > 3,600 (Physically Impossible) ⚠️

> **FACT:** 66,596 rows have `offline_duration_sec` > 3,600. The maximum observed value is **726,642 seconds** (≈ 8.4 days).

- A single telemetry row represents a **one-hour window**.
- A gateway cannot be offline for more than 3,600 seconds within a one-hour window.
- **Interpretation (hypothesis):** These extreme values may represent a **cumulative counter** (offline time since last reboot / since last report) that was placed in a slot labelled as "per-hour duration". Or, they could indicate the telemetry is reported *after* a prolonged outage and the value reflects the total outage time.
- The same gateways appear repeatedly with value 726,642 — this looks like a sentinel/overflow value.

**Caution:** Do not aggregate `offline_duration_sec` naively. Consider capping or log-transforming, or using `disconnection_cnt` as a safer indicator.

---

### 2.4 All 320 Gateways Have Missing Hours

> **FACT:** Every single gateway has at least 20 missing hours in its telemetry record.

| Statistic | Value |
|---|---|
| Min missing hours | 20 |
| Median missing hours | 417 |
| Mean missing hours | 676 |
| Max missing hours | **4,041 (69.3%)** for gateway `02C0F45F31E7` |

- **Interpretation:** Missing hours are likely periods where the gateway was completely offline and unable to report telemetry (not just disconnected from meters). However, gaps could also be caused by a late installation date.
- One gateway (`06903F988F32`) appears to have data for only 548 out of 1,248 expected hours (44%), suggesting it may have been installed partway through the study period.

---

### 2.5 Telemetry Sample vs Parquet: Coverage Difference

> **FACT:** The August 2025 sample CSV has **280 unique gateways**, while the parquet for the same month shows 320.

- **Interpretation:** The sample may be a filtered export (e.g., a specific tenant or region). It is not a complete copy of the August telemetry. Do not use the CSV sample as a substitute for the parquet data.

---

### 2.6 Gateway Master: 12 Gateways Without Telemetry ⚠️

> **FACT:** 12 gateways appear in `gateway_master` but have **no telemetry** in the partitioned parquet.

- Checking `decommissioned_on`: 12 gateways have a non-null decommission date, matching the count precisely.
- **Interpretation:** These are decommissioned gateways. They should be excluded from any scoring or ranking for the prediction weeks.

---

### 2.7 Engineer Review: Single Reviewer, Perfectly Balanced Labels

> **FACT:** All 120 review records were written by "M. Hoffmann". The split is exactly 60 Schlecht / 60 Normal.

- **Caution:** A perfectly balanced label set from a single reviewer is unusual in production data. It may have been constructed for the challenge by design.
- The review is for **February 2026 only** and covered only 120/320 gateways (~37.5%).
- 46 of 120 entries (38%) have no `Bemerkung` (comment).

---

### 2.8 Meter Read Success: No Impossibles, But Many Low Weeks

> **FACT:** No row has `read_rate > 1.0` (impossible). No row has `meters_expected = 0`.

- Mean read rate: **84.5%**; median: **90.9%**
- **567 rows (7.8%)** have read_rate < 50% — these are severe underperformance events.
- 22 gateways have fewer than 13 weeks of data (< 50% of the 26-week study period) — they may be recently installed or decommissioned.
- 7.0% of possible gateway-week combinations are missing entirely — primarily from gateways that joined late.

---

### 2.9 Counter Behaviour: Suspicious High Values

> **FACT:**
> - `reboot_cnt` can be **32** in one hour (physically possible? Maybe during catastrophic OOM loops)
> - `disconnection_cnt` can be **55** in one hour
> - `r_cnt_power_cycle`, `r_cnt_reboot`, `r_cnt_unknown` all reach 32

- 1,913 rows have `reboot_cnt > 5`; 1,003 rows have `reboot_cnt > 10`
- **Caution:** These may be legitimate (e.g., firmware crash loops), but they could also be counter roll-overs or saturation artefacts. Do not assume a value of 32 means exactly 32 reboots.

---

## 3. Important Distributions and Patterns

### Telemetry Health Fields (2025-08 to 2026-03)

| Field | % Zero | Mean (non-zero) | Max |
|---|---|---|---|
| `offline_duration_sec` | 77.3% | ~8,200s | 726,642 |
| `disconnection_cnt` | 77.3% | ~3.4 | 55 |
| `reboot_cnt` | 98.4% | ~2.6 | 32 |
| `reboot_duration_sec` | 98.4% | ~434s | 1,027,864 |
| `r_cnt_power_cycle` | 99.8% | very rare | 32 |
| `r_cnt_reboot` | 99.5% | very rare | 32 |
| `r_cnt_unknown` | 99.1% | very rare | 32 |
| `no_conn_importance` | 77.3% | high variance | 51.3M |
| `reboot_importance` | 98.4% | high variance | 40.0M |

Most hours, for most gateways, **nothing bad happens.** The distribution is extremely right-skewed. Any aggregation or anomaly detection must account for this.

### Gateway Master

- **4 tenants**: tenant_a (58%), tenant_b (22%), tenant_c (13%), tenant_d (7%)
- **5 site types**: Gebäude (building) 45%, Heizraum (boiler room) 18%, Außenmast (outdoor mast) 16%, Schaltschrank (switchbox) 14%, Kellerraum (cellar) 7%
- **6 German states (Länder)**: Bayern, NRW, Baden-Württemberg, Hessen, Niedersachsen, Sachsen
- **4 hardware models**: GW-2100 (55%), GW-2100L (30%), GW-3400 (14%), GW-8800X (1 unit – unusual)
- **4 firmware versions**: 3.2.0, 2.15.1, 3.3.1, 2.14.3
- **Meters installed**: mean=189, min=40, max=822 (the stakes differ a lot by gateway)
- **180 gateways (54%)** have no `fw_updated_on` date — firmware version is stale/untracked

### Field Visits

- **7 reasons** (in German): 
  - Häufige Neustarts (frequent reboots) – 17.1%
  - Kunde meldet Ausfall (customer reports outage) – 15.7%
  - Keine Verbindung (no connection) – 15.6%
  - Auffällige Statistik (suspicious stats) – 13.6%
  - Zähler nicht gelesen (meter not read) – 13.4%
  - Signal schwach (weak signal) – 12.3%
  - Routineprüfung (routine check) – 12.3%
- **3 outcomes**:
  - Kein Fehler gefunden (no fault found) – **60.7%** ← majority of visits found nothing!
  - Fehler behoben (fault fixed) – 34.7%
  - Kein Zugang (no access) – 4.5%
- **Parts replaced** (only 25.9% of visits): Netzteil (PSU), Antenne, Kabel, Gateway getauscht (full replacement), SIM-Karte

The **60.7% false-alarm rate** from historical visits is a critical baseline to beat.

---

## 4. Interesting Relationships

### 4.1 Schlecht vs Normal: Telemetry in February 2026

> **OBSERVED FACT** (Feb 2026 telemetry, per-gateway means):

| Metric | Schlecht (54 gws) | Normal (56 gws) | Ratio |
|---|---|---|---|
| `offline_duration_sec` | **28,007** | 943 | ~30× |
| `disconnection_cnt` | **5.80** | 0.33 | ~18× |
| `reboot_cnt` | **0.21** | 0.03 | ~7× |
| `no_conn_importance` | **1,337,477** | 3,643 | ~367× |
| `reboot_importance` | **11,210** | 35 | ~320× |

> **Interpretation:** The Schlecht/Normal labels are strongly associated with telemetry degradation. The `no_conn_importance` and `offline_duration_sec` signals appear especially powerful for discriminating problem gateways.

---

### 4.2 Schlecht vs Normal: Meter Read Rate

> **OBSERVED FACT:**

| Label | Mean read rate | Median | % rows < 90% read rate |
|---|---|---|---|
| Schlecht | **78.1%** | 86.2% | 71.4% |
| Normal | **82.6%** | 90.2% | 48.6% |

> **Interpretation:** Schlecht gateways do read fewer meters on average, but the difference is smaller than the telemetry signal — some Schlecht gateways still achieve decent read rates. Meter read rate is a **lagging indicator** (you see the meter failure *after* the gateway problem). It is still useful but may not be the most discriminating signal.

---

### 4.3 Schlecht vs Normal: Field Visit History

> **OBSERVED FACT:**
> - 83% of Schlecht gateways have at least one field visit in the historical record
> - 77% of Normal gateways have at least one field visit

> **Interpretation:** Schlecht gateways are only slightly more likely to have been visited than Normal gateways. This could mean: (a) visits don't reliably fix problems, or (b) the review labels don't align closely with historical visit reasons.

---

### 4.4 `avg_reboot_duration` Implying Extended Downtime

> **FACT:** `reboot_duration_sec` max is 1,027,864 seconds (~11.9 days). `avg_reboot_duration` max is 43,160 seconds.

Just like `offline_duration_sec`, this appears to be a cumulative or total counter, not a per-hour duration. It should be treated with caution.

---

### 4.5 Network/Radio Columns Available

The telemetry schema includes:
- `rssi_good`, `rssi_normal`, `rssi_bad` (hours per bucket)
- `rscp_rsrp_good`, `rscp_rsrp_normal`, `rscp_rsrp_bad`
- `ecio_rsrq_good`, `ecio_rsrq_normal`, `ecio_rsrq_bad`
- `network_2g`, `network_3g`, `network_4g`, `network_unknown`
- `operator_*` columns (TelekomDE, VodafoneDE, etc.)
- Load/memory: `avg_load1`, `avg_memfree`, `avg_idletime`, `avg_uptime`

These have not been analyzed in depth yet.

---

## 5. Things to Be Careful About

1. **`offline_duration_sec` > 3,600 is not a per-hour measurement.** It is likely cumulative. Naive summation or averaging will produce misleading numbers. Consider capping at 3,600 or using log-scale.

2. **Duplicate row deduplication required.** The 6,547 duplicate rows are exact copies and should be dropped before any analysis or feature engineering.

3. **Gateway ID format must be normalized.** Compact hex (telemetry, MRS) vs colon-MAC (master, visits, review). Always strip colons and uppercase before joining.

4. **Missing telemetry ≠ "gateway was fine."** A completely offline gateway produces no telemetry rows. A gateway with many missing hours is likely *more* problematic, not less.

5. **`telemetry_sample_2025-08.csv` is not a complete August extract.** It covers only 280/320 gateways and should not be used as a substitute for the parquet partitions.

6. **Engineer review covers only 120/320 gateways.** Predictions must be made for all ~320. We cannot rely on the Schlecht/Normal label alone.

7. **The 60/60 Schlecht/Normal split from a single reviewer looks engineered.** Treat these labels as useful signal, not as ground truth. They reflect the reviewer's opinion at a point in time.

8. **"Kein Fehler gefunden" (no fault found) is 60.7% of historical visits.** A good ranking algorithm should avoid sending the field team to gateways that look suspicious but are actually fine.

9. **12 decommissioned gateways** appear in `gateway_master` but not in telemetry. Exclude them from predictions.

10. **n_meters_installed** ranges from 40 to 822. A failing gateway with 800+ meters is vastly more impactful than one with 40. The score should arguably incorporate gateway importance/scale.

---

## 6. Initial Hypotheses for "Needs a Visit"

| # | Hypothesis | Evidence | Type |
|---|---|---|---|
| H1 | Gateways with high `offline_duration_sec` (capped at 3,600) or high `disconnection_cnt` need visits | Schlecht gateways show 30× more offline_sec | Supported by data |
| H2 | `no_conn_importance` is a strong composite signal — high values strongly indicate a problem | 367× ratio Schlecht vs Normal | Supported by data |
| H3 | A *worsening trend* matters more than a high absolute value, especially for gateways with naturally noisy behaviour | Baseline 3-sigma approach implicitly tests this | Hypothesis only |
| H4 | Gateways with many meters (high `n_meters_installed`) should be weighted higher | Business logic (costs are per-meter) | Hypothesis |
| H5 | Poor meter read rate is a lagging indicator that confirms the need for a visit, not the primary predictor | MRS signal exists but lags telemetry signal | Supported partially |
| H6 | Reboot-class signals (`reboot_cnt`, `r_cnt_power_cycle`) identify hardware/firmware problems that require part replacement | 34.7% of visits resulted in part replacement | Hypothesis |
| H7 | Gateways with significant missing telemetry (gap hours) are very likely offline and need a visit | 69% missing hours for worst gateway | Hypothesis |
| H8 | Older firmware versions may correlate with higher failure rates | 180 gateways have no fw_updated_on | Needs further analysis |
| H9 | Outdoor mast (Außenmast) and Schaltschrank site types have different failure modes than indoor Gebäude | Site types span 5 categories | Needs further analysis |

---

## 7. Unanswered Questions

1. **What do the "network_2g/3g/4g/unknown" hours represent?** Do 2G-only hours correlate with more failures?
2. **Are the rssi_good/normal/bad fields counts of hours or signal-strength values?** The naming implies counts.
3. **Does `avg_uptime` represent continuous uptime since last reboot?** If so, very short avg_uptime indicates frequent reboots even when `reboot_cnt` appears low.
4. **Why does `offline_duration_sec` sometimes exceed 3,600?** Is it intentional (cumulative counter) or a bug?
5. **How should we handle gateways with <4 weeks of telemetry in a prediction window?** The baseline uses 28 days, so new gateways have insufficient history.
6. **Do the 22 gateways with <13 weeks of meter_read data need special treatment?**
7. **Is the `Routineprüfung` category in field visits part of a scheduled programme?** If so, those visits are not anomaly-driven and may distort our visit-success rate.
8. **What causes the large telemetry gaps?** Are gaps concentrated around certain dates (weather events, network outages)?
9. **Do gateways that were visited (and fixed) subsequently show improved telemetry?** This would help validate our signal.
10. **Which of the 12 decommissioned gateways overlap with the scored weeks?** Some have a decommission date within the scored period.

---

## 8. Terminology Glossary (Notable German Field Values)

| German | English |
|---|---|
| Gebäude | Building |
| Heizraum | Boiler/heating room |
| Außenmast | Outdoor mast/pole |
| Schaltschrank | Distribution cabinet |
| Kellerraum | Cellar/basement |
| Schlecht | Bad/Poor |
| Häufige Neustarts | Frequent reboots |
| Keine Verbindung | No connection |
| Kein Fehler gefunden | No fault found |
| Fehler behoben | Fault repaired |
| Kein Zugang | No access |
| Routineprüfung | Routine inspection |
| Netzteil | Power supply unit |
| unauffällig | Unremarkable/normal |
| seit Monaten auffällig | Has been problematic for months |
