# Optimization V1 Forensic Audit Report

**Date:** 2026-09-10  
**Target:** Optimization V1 gateway ranker (`src/part1/ranker_optimized.py`), `predictions_optimized.csv`, `evaluate.py`, and validation framework  
**Branch:** `test`  
**Working tree status:** No production code modified, no CSVs modified, working tree clean.

---

## 1. Executive Verdict

### Verdict: **SUSPICIOUS BUT FIXABLE**

The optimizer is **not fundamentally broken** in terms of leakage, logic inversion, or illegal operations. It genuinely detects the most critically impaired gateways in the network. However, the audit reveals **two significant design flaws** and **one major evaluation reporting distortion**:

1. **Denom-Skewed Persistence Bug / Artifact:**  
   Persistence is calculated as `problem_hours / coverage_hours`. Gateways that are almost completely dead report very few telemetry hours (e.g., 22–38 hours instead of 168). Every reported hour shows a fault, yielding an automatic `1.0` (100%) persistence, whereas healthy or mildly degraded gateways have 168 observed hours. Thus, low telemetry coverage acts as a force multiplier for 100% persistence.
2. **Visit-Feedback Amnesia (Business Objective Mismatch):**  
   The optimizer operates with an independent 7-day memory each Monday with zero awareness of previous visit dispatches. Because a permanently dead gateway continues to fail every single week, the optimizer sends technicians back to the same 7 gateways all 8 weeks (consuming 56 of the 120 total visits). While technically justified under a static ranking model, in reality sending 8 consecutive weekly visits to the same site without waiting for a fix violates operational common sense.
3. **Evaluation Reporting Distortion (92 vs 22 Schlecht):**  
   The headline metric of "92 Schlecht visits" is mathematically real at the visit-row level, but **substantially inflated by repeat counting**. There are only 60 total Schlecht gateways in the entire February engineer review. The optimizer targets **20 unique Schlecht gateways**, visited on average 4.6 times each ($20 \times 4.6 = 92$). It does not identify 92 different broken gateways.

---

## 2. Evidence for the Verdict

| Dimension | Assessment | Key Evidence |
|---|---|---|
| **Temporal Leakage** | **CLEAN (Safe)** | Filtering strictly enforces `ts < Monday 00:00 UTC`. `BASELINE_DAYS` (28d) is instantiated strictly in `[end - 28d, end)` and `RECENT_DAYS` in `[end - 7d, end)`. Zero leakage from future telemetry, MRS, or engineer reviews. |
| **Data Integrity & Eligibility** | **CLEAN (Safe)** | Active gateways are correctly verified using install/decommission dates from `gateway_master.csv`. ID normalisation is consistent. |
| **Persistence Definition** | **FLAWED** | `persistence = problem_hours / coverage_hours`. Correlates with coverage at $r = -0.75$. Unreported hours are omitted from denominator. |
| **Visit Allocation** | **DEBATABLE** | 7 gateways consume 56 out of 120 visits. Only 31 unique gateways are visited across 8 weeks. |
| **Score Compression** | **EXPLAINED** | Scores cluster between 1.53 and 1.83 because only the extreme right-tail (top 5% of network) is selected, where normalized terms approach 1.0. |
| **Evaluation Headline** | **MISLEADING** | "92 Schlecht" counts repeat visits to 20 unique gateways. Baseline's "22 Schlecht" counts repeat visits to 12 unique gateways. |

---

## 3. Exact Score Decomposition for 5 Representative Gateways

We manually traced 5 representative gateways across three distinct weeks:
- **02C0F45F31E7** (Selected all 8 weeks, Rank 2–9)
- **02892F51E1CB** (Selected all 8 weeks, Rank 3–13)
- **069A98DEEB1D** (Selected 1 week in Feb 2, dropped out later)
- **0E9A30D927A5** (Selected 1 week in Feb 2, dropped out later)
- **02D7623552C8** (Selected all 8 weeks, boundary rank 15 on Feb 2, climbs to Rank 2 on Mar 23)

### Trace: Week 2026-02-02 (Week 1)

| Gateway | Rank | Raw Offline (s) | Raw Disc | Coverage (hrs) | Prob Hrs | Tech Off Norm | Tech Disc Norm | Technical ($0.6/0.4$) | Persistence | Corrob | Exposure (Meters) | Final Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **02C0F45F31E7** | 2 | 14,045,475 | 1,760 | 32 | 32 | 1.0000 | 0.9767 | 0.9907 | 1.0000 | 1.0000 | 0.6451 (75m) | **1.7792** |
| **02892F51E1CB** | 3 | 5,762,679 | 2,103 | 49 | 49 | 0.9459 | 1.0000 | 0.9675 | 1.0000 | 0.9434 | 0.7228 (127m) | **1.7720** |
| **069A98DEEB1D** | 6 | 2,914,978 | 727 | 62 | 62 | 0.9045 | 0.8613 | 0.8872 | 1.0000 | 0.8614 | 0.8301 (262m) | **1.6980** |
| **0E9A30D927A5** | 12 | 1,675,161 | 321 | 88 | 86 | 0.8708 | 0.7547 | 0.8244 | 0.9773 | 0.7773 | 0.8507 (301m) | **1.5979** |
| **02D7623552C8** | 15 | 652,431 | 490 | 102 | 100 | 0.8135 | 0.8098 | 0.8120 | 0.9804 | 0.7326 | 0.7382 (141m) | **1.5301** |

### Trace: Week 2026-02-23 (Week 4)

| Gateway | Rank | Raw Offline (s) | Raw Disc | Coverage (hrs) | Prob Hrs | Technical | Persistence | Corrob | Exposure | Final Score |
|---|---|---|---|---|---|---|---|---|---|---|
| **02C0F45F31E7** | 9 | 7,343,278 | 1,210 | 22 | 22 | 0.9408 | 1.0000 | 0.9818 | 0.6451 | **1.7154** |
| **02892F51E1CB** | 4 | 6,513,086 | 2,021 | 44 | 44 | 0.9626 | 1.0000 | 0.9677 | 0.7228 | **1.7719** |
| **069A98DEEB1D** | *Unranked* | 65,704 | 95 | 129 | 62 | 0.6389 | 0.4806 | 0.5809 | 0.8301 | **1.1232** |
| **0E9A30D927A5** | *Unranked* | 97,940 | 63 | 135 | 48 | 0.6328 | 0.3556 | 0.5911 | 0.8507 | **1.0766** |
| **02D7623552C8** | 5 | 8,650,535 | 1,179 | 37 | 37 | 0.9455 | 1.0000 | 0.9731 | 0.7382 | **1.7591** |

### Why Did They Receive Their Scores?
- **02C0F45F31E7 and 02892F51E1CB:** Millions of offline seconds and thousands of disconnections in every single week. Telemetry arrives only ~20–50 hours/week, and in 100% of those packets, the gateway is in severe distress. Their technical score is near 1.0, persistence is 1.0, corroboration is ~0.95–1.0. Final score is locked at $\approx 1.75–1.78$.
- **069A98DEEB1D and 0E9A30D927A5:** In Week 1, they were failing severely (persistence $>97\%$). By Week 4, their coverage normalized to 129–135 hours and their problem hours dropped to 48–62 hours (persistence fell to 35–48%). Their score dropped from ~1.65 to ~1.08, dropping them cleanly out of the Top 15. This proves the optimizer is dynamic and **does not permanently trap gateways** if they recover.
- **02D7623552C8:** Started with moderate issues in Week 1 (Rank 15), but deteriorated dramatically by Week 4 (offline duration jumped from 652k to 8.65M seconds), pushing its rank up from 15 to 5.

---

## 4. Persistence Analysis: The 100% Persistence Claim

### How "Elevated" Is Defined in Code
Lines 115–127 and 135–137 of `src/part1/ranker_optimized.py`:
```python
has_offline = recent["offline_duration_sec"] > 0
has_disc = recent["disconnection_cnt"] > 0
has_problem = has_offline | has_disc
problem_hours = has_problem.groupby(recent["gateway_id"]).sum()
persistence = (recent_agg["problem_hours"] / np.maximum(recent_agg["coverage_hours"], 1)).clip(0, 1)
```

### Forensic Findings:
1. **Elevated relative to what?**
   - It is **not** relative to baseline mean or standard deviation.
   - It is an **absolute condition**: any hour where `offline_duration_sec > 0` OR `disconnection_cnt > 0`.
2. **Missing data and denominator skew:**
   - A full 7-day week contains 168 hours. Healthy gateways typically report 155–167 hours.
   - Highly broken gateways drop packets and only report 20–50 hours.
   - The denominator is `coverage_hours` (actual observed hours), **not 168**.
   - If a gateway only transmits 25 packets all week, and every packet reports `offline_duration_sec > 0`, its persistence is $\frac{25}{25} = 1.0$ (100%).
   - The correlation across the entire network between `coverage_hours` and `persistence` is strongly negative: **$r = -0.67$ to $-0.81$**.
3. **Does the code confuse baseline and recent?**
   - No. Line 104 defines `window` over 28 days, but line 107 slices `recent = window[window["ts"] >= end - 7d]`. The aggregation is performed strictly over `recent`.
4. **Is 100% persistence real failure?**
   - Yes. These gateways are genuinely crippled: their historical meter read rate is abysmal (e.g. `02C0F45F31E7` has an 8% read rate, and `022C6F326E3B` has 14%).
   - However, describing it as "elevated across 100% of hours" is linguistically misleading to an operator because the gateway was actually missing/silent for 130+ of the 168 hours.

---

## 5. Repeated Selections Analysis

Across all 8 weeks (120 visit slots):
- **Total unique gateways visited:** **31** (compared to 74 in the 3-sigma baseline).
- **Week-over-week Top 15 overlap:** **11 to 14 gateways out of 15** persist from one week to the next.
- **Repeat frequency:**
  - **7 gateways** selected in all 8 weeks (consuming **56 visits**, 46.7% of total operational capacity).
  - **10 gateways** selected $\ge 6$ weeks (consuming **74 visits**, 61.7% of total visits).
  - **15 gateways** selected $\ge 4$ weeks.
  - **11 gateways** selected only once.

### Are Repeated Gateways Genuinely Broken?
Yes, conclusively:
- All 7 gateways visited 8 times are confirmed severe failures:
  - 6 are explicitly categorized as **Schlecht** in the independent engineer review (the 7th was unreviewed).
  - Their historical meter read rates are severely depressed (e.g. 8%, 14%, 45%, 47%).
  - None of them are "normal" false alarms.

### Why Does Repetition Happen?
The ranking formula has **no memory of previous visit dispatches** (cooldown / dispatch tracking). Because field visits recorded in `field_visits.csv` only run through February 14, 2026, there is no real-world closure label for visits dispatched in late February or March. Without a dispatch penalty or cooldown mechanism, a gateway that stays broken will naturally top the technical severity ranking every single week.

---

## 6. Score Distribution Analysis

### Why are scores compressed in 1.53 – 1.83?
- Across the entire network ($N = 2,390$ gateway-weeks), scores span the entire range from **0.00 to 1.83**:
  - Minimum: `0.00`
  - 25th percentile: `0.65`
  - Median (50th percentile): `0.79`
  - 75th percentile: `1.04`
  - 90th percentile: `1.38`
  - 95th percentile: `1.56`
  - Top 15 (selected): `1.53 – 1.83`
- The scores of the selected gateways appear compressed solely because **only the top 5% extreme right tail** of the entire network is selected.

### Component Decomposition for Top 15 Gateways:
- `technical`: $\sim 0.85 - 0.99$ (due to log1p scaling on millions of offline seconds)
- `persistence * 0.3`: $\sim 0.28 - 0.30$ (persistence is near 1.0)
- `corroboration * 0.2`: $\sim 0.16 - 0.20$ (high `no_conn_importance`)
- `evidence` subtotal: $\approx 1.30 - 1.49$
- `exposure multiplier`: $1 + 0.3 \times \text{log\_meters} \approx 1.20 - 1.25$
- Final score: $\approx 1.35 \times 1.23 \approx 1.65 - 1.80$.

The exposure multiplier is modest ($+20\%$ to $+25\%$), ensuring that business impact tilts the ranking among severely broken gateways without promoting healthy gateways with many meters.

---

## 7. Temporal Leakage Audit

A line-by-line inspection of `src/part1/ranker_optimized.py`, `data_loader.py`, and `eligibility.py` confirmed:

1. **Monday Cutoff:**  
   `end = pd.Timestamp(monday, tz="UTC")`  
   `window = frame[(frame["ts"] >= end - dt.timedelta(days=BASELINE_DAYS)) & (frame["ts"] < end)]`  
   Strict inequality `< end` prevents any timestamp from Monday 00:00:00 UTC onward from entering calculations.
2. **Meter Reads:**  
   `meter_read_success.csv` is **not loaded or used** anywhere in `ranker_optimized.py` or `data_loader.py`.
3. **Engineer Review:**  
   `engineer_review_2026-02.xlsx` is **not imported or referenced** in production code. It is used exclusively in `evaluate.py`.
4. **Field Visits:**  
   `field_visits.csv` is **not loaded or used** in the ranking pipeline.
5. **Eligibility:**  
   `active_gateways()` correctly checks `installed_on < monday` and `(decommissioned_on is None or decommissioned_on >= monday)`.

**Verdict: 100% Leakage-Free.**

---

## 8. Evaluation Methodology Audit

### Is the Headline "92 Schlecht vs 22 Schlecht" Fair?
The comparison in `evaluate.py` calculates metrics on the **120 row selections**, not on unique gateways:
- The engineer review contains **120 unique gateways** (60 Schlecht, 60 Normal) reviewed as a snapshot on `2026-02-15`.
- In `predictions_optimized.csv`:
  - **20 unique Schlecht gateways** are selected.
  - Because these 20 gateways are selected repeatedly across multiple weeks, they generate **92 Schlecht visit rows**.
  - **4 unique Normal gateways** are selected (each selected exactly once), generating **4 Normal visit rows**.
  - **7 unique unreviewed gateways** are selected, generating 24 visit rows.
- In `predictions_baseline.csv`:
  - **12 unique Schlecht gateways** are selected, generating **22 visit rows**.
  - **15 unique Normal gateways** are selected, generating **26 visit rows**.
  - **47 unique unreviewed gateways** are selected, generating 72 visit rows.

### Methodological Issues Identified:
1. **Temporal Asymmetry:** The review occurred on `2026-02-15`. Using this snapshot to evaluate predictions in late March assumes that gateway health is static across the entire 8-week period.
2. **Pseudo-Replication:** Counting the same gateway 8 times inflates the apparent sample size of the evaluation from 20 to 92.
3. **True Performance:** Even on a **unique gateway** basis, Optimization V1 is objectively superior:
   - Optimized: 20 Schlecht vs 4 Normal (Unique S/N = **5.00**)
   - Baseline: 12 Schlecht vs 15 Normal (Unique S/N = **0.80**)

---

## 9. Business Objective Audit

The business parameters are:
- Wasted visit: $\approx €380$
- Unattended broken gateway: $\approx €600$ per week
- Capacity: 15 visits per week

### Alignment Assessment:
1. **False Alarm Avoidance:**  
   Optimization V1 successfully cuts wasted visits to known healthy gateways from 26 down to 4 (saving $\approx 22 \times €380 = €8,360$).
2. **Repeat Visits Without Cooldown:**  
   Sending technicians to the exact same gateway 8 weeks in a row without confirmation of repair is economically questionable. If a gateway was visited in Week 1 and cannot be repaired until replacement hardware arrives in 3 weeks, visiting it again in Week 2 and Week 3 wastes $€380$ each time.
3. **However, within Part 1 Constraints:**  
   The challenge explicitly defines Part 1 as a **static per-week ranking based purely on operational telemetry**:
   > *"Part 1 is a pass/fail gate. Do not spend Part 1 effort on unnecessary ML or application features... For each prediction Monday, examine the most recent 7 days... rank descending... select the top 15."*  
   The challenge specification did not ask for a dynamic visit simulator or closed-loop state machine.

---

## 10. Specific Deficiencies Identified

| ID | Issue | Severity | Impact |
|---|---|---|---|
| **BUG-01** | **Coverage/Denominator Distortion in Persistence** | **Medium** | Calculating `problem_hours / coverage_hours` gives a silent gateway with 10 packets the same 100% persistence as a gateway with 168 continuously observed failing hours. |
| **BUG-02** | **Misleading Reason Wording** | **Low** | Reasons state "elevated across 100% of 22 observed hours", which can confuse operators who expect 168 hours in a week. |
| **BUG-03** | **Unused Baseline Variable** | **Cosmetic** | `window` calculates 28 days of history in `ranker_optimized.py`, but only `recent` (7 days) is actually used. The 28-day slice is redundant. |
| **METH-01** | **Evaluation Metric Overcounting** | **Reporting** | Headline evaluation in `evaluate.py` reports visit-row counts without clarifying unique gateway counts. |

---

## 11. Recommended Fixes (Ranked by Priority)

### Recommendation 1: Fix Persistence Denominator & Missingness (Medium Priority)
Instead of dividing by `coverage_hours`, factor in expected hours ($168$) or blend coverage penalty:
$$\text{persistence} = \frac{\text{problem\_hours}}{\text{coverage\_hours}} \times \left(\frac{\text{coverage\_hours}}{168}\right)^{\alpha}$$
Alternatively, count missing telemetry explicitly as an operational failure signal rather than an invisible denominator reduction.

### Recommendation 2: Transparent Reporting in `evaluate.py` (Low Priority)
Update `evaluate.py` to output **both** visit-level counts and unique-gateway counts:
- *Visit-level:* 92 Schlecht / 4 Normal
- *Unique-gateway level:* 20 Schlecht / 4 Normal

### Recommendation 3: Clean up Dead Code in `ranker_optimized.py` (Low Priority)
Remove lines 103–106 that compute the 28-day window if it is not used in the formula, keeping only the 7-day slice.

### Recommendation 4: Clarify Reason String (Low Priority)
Change reason string from:
`"persistent offline_duration_sec elevated across 100% of 32 observed hours; 75 meters exposed"`
to:
`"Critical failure: 32/32 observed hours impaired (136h silent); 75 meters exposed"`.

---

## Conclusion
The optimizer's high scores, repeated selections, and 100% persistence claims are **not a catastrophic calculation error or data leakage**. They reflect the reality that **the network has a core group of ~20 severely malfunctioning gateways that drop most packets and fail continuously every week**. The optimizer detects these relentlessly. 

With minor refinements to persistence normalization and reason clarity, Optimization V1 is sound, robust, and defensible.
