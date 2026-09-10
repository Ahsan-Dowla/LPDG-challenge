# Part 1 --- Implementation Specification

## Objective

Implement Part 1 of the LPDG Innovation Hub Selection Challenge without
rebuilding the existing exploration work.

The current repository already contains:

-   `explore.py`
-   `docs/problem-understanding.md`
-   `docs/data-exploration.md`
-   `baseline_3sigma.py`
-   `validate_submission.py`

The implementation must turn the current analysis into a reproducible
weekly ranking pipeline that produces the required `predictions.csv`.

Part 1 is a **pass/fail gate**. Do not spend Part 1 effort on
unnecessary ML or application features. The supplied 3-sigma baseline is
valid and may be retained. The implementation should prioritize
correctness, temporal integrity, reproducibility, and clear decisions.

------------------------------------------------------------------------

## 1. Required Output

Generate:

`predictions.csv`

with exactly these columns:

``` text
week_start
rank
gateway_id
score
reason
```

Required weeks:

``` text
2026-02-02
2026-02-09
2026-02-16
2026-02-23
2026-03-02
2026-03-09
2026-03-16
2026-03-23
```

For every week:

-   exactly 15 gateways
-   ranks exactly `1..15`
-   no duplicate gateway within a week
-   numeric, non-empty score
-   non-empty reason
-   reason \<= 300 characters

Total:

``` text
8 weeks × 15 gateways = 120 rows
```

Run:

``` bash
python validate_submission.py predictions.csv
```

before considering Part 1 complete.

------------------------------------------------------------------------

## 2. Prediction Contract

For a week beginning on Monday `W`, only information available
**strictly before Monday 00:00** may be used.

Do not use:

-   telemetry from `W` or later
-   meter-read data from `W` or later
-   field visits requested/visited after the cutoff
-   engineer reviews that did not exist by the cutoff

The supplied baseline uses Monday 00:00 UTC as its boundary. Keep this
convention consistently across the implementation and document it.

The eight prediction weeks are the scored window defined above.

------------------------------------------------------------------------

## 3. Data Loading

Default data location:

``` text
data/
```

The implementation must also accept an alternate data path, for example:

``` bash
python <entrypoint>.py --data /somewhere/else --out predictions.csv
```

Use the partitioned Parquet telemetry as the primary telemetry source:

``` text
data/telemetry/**/*.parquet
```

Do not use:

``` text
telemetry_sample_2025-08.csv
```

as a substitute for the complete telemetry dataset.

------------------------------------------------------------------------

## 4. Gateway ID Normalisation

The datasets contain two gateway-ID representations:

-   compact 12-character hexadecimal ID
-   colon-separated MAC-style ID

Canonicalise IDs before joining:

``` python
def normalize_gateway_id(value):
    return str(value).strip().replace(":", "").upper()
```

Apply this consistently to:

-   telemetry
-   gateway master
-   meter read success
-   field visits
-   engineer review

Never rely on raw formatting when joining datasets.

------------------------------------------------------------------------

## 5. Data Quality Handling

The exploration already identified several important data-quality
issues. Handle them deliberately.

### 5.1 Duplicate telemetry

There are exact duplicate `(gateway_id, ts_utc)` rows.

Deduplicate before feature generation:

``` python
telemetry = telemetry.drop_duplicates(
    subset=["gateway_id", "ts_utc"],
    keep="first"
)
```

Because the observed duplicates are value-for-value copies, keeping the
first copy is sufficient.

### 5.2 Decommissioned gateways

Gateways that are no longer in service should not be selected for
visits.

Use:

``` text
gateway_master.decommissioned_on
```

and the prediction cutoff to determine whether a gateway was active.

A gateway decommissioned before the prediction week must be excluded.

### 5.3 Missing telemetry

Do **not** automatically interpret missing telemetry as healthy.

Missing telemetry can itself represent an operational problem, but it
can also result from installation/decommissioning or other data
availability issues.

The implementation should therefore distinguish:

-   gateway not active yet
-   gateway already decommissioned
-   active gateway with telemetry gaps

At minimum, calculate telemetry coverage for the relevant historical
window and make the treatment explicit.

### 5.4 Extreme counter values

The exploration found very large values in:

-   `offline_duration_sec`
-   `reboot_duration_sec`
-   related counter fields

Do not silently assume these are ordinary hourly durations.

For the baseline-compatible ranking, prefer the supplied 3-sigma logic
rather than inventing arbitrary physical caps unless the chosen
implementation explicitly justifies a transformation.

------------------------------------------------------------------------

## 6. Baseline Ranking Strategy

Start with the supplied `baseline_3sigma.py`.

For each prediction Monday:

1.  Take the previous 28 days of telemetry.
2.  Calculate per-gateway mean and standard deviation for:
    -   `offline_duration_sec`
    -   `disconnection_cnt`
    -   `reboot_cnt`
3.  Examine the most recent 7 days.
4.  Flag observations where a metric exceeds the gateway's own mean by
    more than `3 × std`.
5.  Count flagged hours per gateway.
6.  Rank descending by flagged-hour count.
7.  Select the top 15.

Conceptually:

``` text
28-day history
      ↓
gateway-specific baseline
      ↓
last 7 days
      ↓
3-sigma anomaly detection
      ↓
flagged-hour count
      ↓
rank
      ↓
top 15
```

This baseline is explicitly accepted by the challenge. Do not change the
ranking logic merely for the sake of changing it.

------------------------------------------------------------------------

## 7. Important Implementation Improvement

The supplied baseline has a subtle design limitation: it requires enough
ranked gateways with telemetry but does not explicitly model gateway
service status or telemetry coverage.

The Part 1 implementation should therefore wrap the ranking process with
a **candidate eligibility layer**:

``` text
raw telemetry
     ↓
normalise IDs
     ↓
deduplicate
     ↓
apply temporal cutoff
     ↓
determine active gateways
     ↓
ranking strategy
     ↓
top 15
     ↓
predictions.csv
```

Do not allow decommissioned/ineligible gateways into the ranking.

If the ranking strategy itself is kept identical to the supplied
baseline, that is acceptable. The important requirement is that the
output remains valid and the implementation is honest about the choices.

------------------------------------------------------------------------

## 8. Score Definition

The output `score` is an ordinal ranking score.

It does **not** need to represent:

-   probability
-   percentage
-   calibrated risk
-   monetary cost

For the baseline implementation:

``` text
score = flagged_hours
```

Higher score means stronger evidence of recent anomalous behaviour.

Document this definition in `DECISIONS.md`.

------------------------------------------------------------------------

## 9. Reason Generation

Every selected gateway needs a short operational explanation.

For example:

``` text
12 anomalous hours in the last 7 days against this gateway's own 28-day baseline; strongest breach was offline_duration_sec.
```

Rules:

-   \<= 300 characters
-   no raw feature vector dump
-   understandable to an operations manager
-   explain why the gateway was prioritised

The supplied baseline's reason format can be retained.

------------------------------------------------------------------------

## 10. Deterministic Ranking

The ranking must be reproducible.

If two gateways have the same score, use a deterministic tie-breaker,
such as canonical `gateway_id`.

Recommended ordering:

``` text
score DESC
gateway_id ASC
```

This prevents the output from changing between runs because of dataframe
ordering.

------------------------------------------------------------------------

## 11. Suggested Code Structure

Do not over-engineer Part 1 yet.

A clean minimum structure is:

``` text
src/
├── part1/
│   ├── __init__.py
│   ├── config.py
│   ├── data_loader.py
│   ├── preprocessing.py
│   ├── eligibility.py
│   ├── ranker.py
│   ├── output.py
│   └── pipeline.py
│
└── main.py

tests/
└── test_part1.py
```

If the current repository is still small, the existing
`baseline_3sigma.py` may remain the executable implementation
temporarily. Refactoring into this structure can happen when the SDE
layer is built.

The important architectural seam is:

``` text
pipeline
   ↓
ranker
```

so that the ranking implementation can later be replaced without
rewriting the surrounding system.

------------------------------------------------------------------------

## 12. Minimum Tests

Before Part 1 is considered complete, test:

### Output schema

-   required columns exist
-   no unexpected columns

### Weekly constraints

-   exactly 8 weeks
-   exactly 15 rows per week
-   ranks 1--15
-   no repeated gateway per week

### Gateway IDs

-   compact and colon-separated IDs normalise to the same value

### Temporal cutoff

Create a small synthetic dataset containing rows immediately before and
after a Monday boundary and verify that future rows are ignored.

### Duplicate telemetry

Verify that duplicate gateway-hour records do not double-count
anomalies.

### Decommissioning

Verify that a gateway decommissioned before a prediction week cannot be
selected.

### Determinism

Run the pipeline twice and confirm identical output.

------------------------------------------------------------------------

## 13. Validation Commands

The final Part 1 flow should be:

``` bash
python <entrypoint>.py --data data --out predictions.csv
python validate_submission.py predictions.csv
```

Expected validator result:

``` text
predictions.csv: OK
120 ranked gateways for each of 8 weeks
```

Do not proceed to the SDE/DevOps layer until this works reliably from a
clean environment.

------------------------------------------------------------------------

## 14. DECISIONS.md Entries

Part 1 must document at least five deliberate choices.

Recommended choices:

### Decision 1 --- What does "needs a visit" mean?

Working definition:

> A gateway needs a visit when recent operational telemetry provides
> enough evidence of abnormal or worsening behaviour that it should
> receive one of the limited weekly field visits.

Alternative considered:

> Predict only gateways that will definitely fail.

Reason rejected:

> The supplied data does not provide a direct future-failure label, and
> the operational decision is a ranking under a fixed 15-visit capacity.

### Decision 2 --- Detection vs prediction

Choose explicitly whether the system prioritises:

-   currently abnormal gateways
-   gateways likely to become faulty

If retaining 3-sigma, describe it primarily as **recent anomaly-based
prioritisation**.

### Decision 3 --- Temporal boundary

Use:

``` text
Monday 00:00 UTC
```

and use information strictly before that boundary.

### Decision 4 --- Handling duplicates

Exact duplicate gateway-hour telemetry rows are deduplicated before
analysis.

### Decision 5 --- Active gateway eligibility

Gateways that were already decommissioned at the prediction cutoff are
excluded.

### Part 2 choice

State:

> **Part 2 focus: DevOps**

Software-development practices are used as the foundation, while the
deep specialization is operational reliability, reproducibility, CI/CD,
containerisation, health checks, logging, configuration, and debugging.

------------------------------------------------------------------------

## 15. What NOT to Do in Part 1

Do not:

-   upload the dataset anywhere
-   commit the dataset
-   use future data
-   use the engineer review before it existed
-   treat field visits as perfect ground truth
-   build unnecessary ML
-   build a frontend
-   add cloud dependencies
-   require internet access
-   require API keys
-   make the ranking dependent on a laptop-specific path
-   spend most of the project trying to beat the baseline

The challenge explicitly states that the baseline can be used unchanged
for software development and DevOps, and that Part 1 is primarily a
gate.

------------------------------------------------------------------------

## 16. Definition of Done

Part 1 is complete only when all of the following are true:

-   [ ] Data loads from `data/`
-   [ ] Alternate data path works
-   [ ] Gateway IDs are normalised
-   [ ] Duplicate telemetry is handled
-   [ ] Temporal cutoff is enforced
-   [ ] Decommissioned gateways are excluded
-   [ ] Ranking runs for all 8 weeks
-   [ ] Exactly 15 gateways are produced per week
-   [ ] `predictions.csv` has exactly 120 rows
-   [ ] `predictions.csv` passes `validate_submission.py`
-   [ ] Scores are deterministic
-   [ ] Reasons are \<=300 characters
-   [ ] At least the required Part 1 tests pass
-   [ ] `DECISIONS.md` documents the important choices
-   [ ] No dataset is committed

After this point, **freeze the Part 1 ranking behaviour** and move to
the SDE + DevOps implementation.

------------------------------------------------------------------------

# Next Stage

Once Part 1 is frozen, build around it:

``` text
Part 1 Ranker
      ↓
Ranking Service
      ↓
FastAPI
      ↓
Tests
      ↓
Docker
      ↓
Environment Configuration
      ↓
Health Checks
      ↓
Logging
      ↓
GitHub Actions CI
      ↓
Runbook
      ↓
Live Debugging Practice
```

The goal is not to make Part 1 complicated.

The goal is to make the working Part 1 **reliable, replaceable,
testable, reproducible, and operationally defensible**.
