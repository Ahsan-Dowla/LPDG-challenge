# AI Usage Transparency Statement

This document explains, honestly and accurately, how AI assistance was used
in the development of this project for the LPDG Innovation Hub Selection
Challenge 2026.

---

## 1. The Role of the Developer

This project was conceived, directed, and validated by the developer.
AI was used as an engineering assistant ? not as the author or decision-maker.

The developer was responsible for:

- **Understanding the challenge** ? reading the specifications, understanding
  what the 8-week evaluation window means, what "exactly 15 gateways per week"
  means operationally, and what the grading criteria required.
- **Identifying what to build** ? deciding that an evidence-based ranking
  approach (not a black-box classifier) was appropriate given sparse, biased
  labels and a small dataset.
- **Core engineering decisions** ? choosing the V1 formula structure,
  deciding which signals to weight (persistence vs. raw severity vs. exposure),
  and choosing the 7-day recent window vs. 28-day baseline.
- **Investigating failures** ? when an early persistence formulation produced
  suspicious results (gateways with only 20 hours of telemetry outranking
  gateways with 168 hours of consistent failures), the developer identified
  the bug, understood the root cause (dividing by coverage_hours rather than
  max(coverage_hours, 168)), and directed the fix.
- **Deciding V1 remains official** ? after evaluating V2 results, the
  developer chose to keep V1 as the official Part 1 submission. V2 was not
  blindly promoted just because backtest metrics looked better. The 8-week
  evaluation window is too short for statistically robust strategy comparison,
  and the developer understood this.
- **Treating V2 as a challenger** ? designing V2 as an explicit experimental
  alternative, not a replacement, and documenting its assumptions honestly.
- **Reviewing and challenging AI-generated output** ? AI-suggested code was
  always run locally, tested with pytest, validated against validate_submission.py,
  and in several cases modified or rejected when it did not meet requirements.
- **Running all verification** ? running pytest, validate_submission.py,
  backtest comparisons, and Docker health checks.
- **Making final decisions** ? on architecture, on which tests to include,
  on what documentation was accurate enough to keep, and on what caveats
  needed to be stated.

---

## 2. How AI Was Used

AI assistance (Google Antigravity / Gemini models) was used as a tool for:

### 2.1 Code Scaffolding and Implementation Assistance

- **Data pipeline**: scaffolding of `data_loader.py`, `eligibility.py`,
  `output.py`, and the gateway ID normalization function.
- **V1 ranker**: implementing the ranking formula, log-normalization,
  persistence calculation, and tie-breaking logic after the developer
  specified the mathematical approach.
- **V2 ranker**: implementing the Bayesian Beta-Binomial persistence model
  and expected-value formula after the developer specified the decision
  framework.
- **API layer**: scaffolding FastAPI routes, Pydantic schemas, and exception
  handlers based on the developer's architectural specification.
- **Architecture refactor**: creating the `src/lpdg/` package structure,
  compatibility bridge layers (`src/services/`, `src/api/`), and the
  `scripts/` CLI entrypoints.

### 2.2 Test Generation and Debugging Support

- Generating unit and integration tests for `test_part1.py`, `test_api.py`,
  and `test_v2_probabilistic.py` based on developer-specified requirements.
- Authoring the dedicated regression test `test_regression_coverage.py`
  protecting against the persistence coverage bug (after the developer
  identified and explained the bug).
- Strengthening the `tests/regression/test_frozen_outputs.py` suite to
  include full column comparison, reason string comparison, and truncation-
  based leakage tests.
- Debugging failures (e.g., date comparison errors, strategy naming
  inconsistencies) by reading tracebacks the developer provided.

### 2.3 Documentation Drafting

- Drafting `README.md`, `docs/architecture.md`, `docs/methodology.md`,
  `docs/runbook.md`, `docs/limitations.md`, `DECISIONS.md` entries,
  and this document ? all reviewed, corrected, and approved by the developer.

### 2.4 Infrastructure

- Authoring `Dockerfile`, `docker-compose.yml`, `.dockerignore`,
  and `.github/workflows/ci.yml` based on developer-specified requirements.

---

## 3. Key Engineering Judgement Stories

These illustrate why human oversight mattered.

### 3.1 The Persistence Coverage Bug

In an early version of the V1 ranker, persistence was computed as:

    persistence = problem_hours / coverage_hours

A gateway that reported only 20 hours in the week (all 20 impaired) achieved
persistence = 1.0 (100%), the same as a gateway continuously failing for the
full 168 hours. This was clearly wrong: the 20-hour gateway had sparse
evidence; the 168-hour gateway had sustained evidence.

The developer identified this anomaly through forensic analysis of ranking
results. The fix:

    persistence = problem_hours / max(coverage_hours, 168)

was specified by the developer and verified through the regression test
`test_regression_coverage.py`.

### 3.2 V1 Remains Official

After V2 was implemented and backtested, the developer reviewed the results
carefully:
- The 8-week official evaluation showed V1 and V2 had identical
  engineer-confirmed visit counts (89 Schlecht each).
- The ~+EUR 23,520 backtest advantage of V2 is a *simulated estimate* on
  historical data, not a realized saving.
- V2 depends on assumed cost parameters (EUR 380 wasted visit, EUR 600
  unattended failure) that are not empirically validated.
- The developer decided that replacing V1 with V2 without stronger evidence
  would be premature. V1 was frozen as the official submission.

### 3.3 Challenging AI Output

Examples where AI-generated suggestions were reviewed and corrected:
- AI initially described V2 as "calibrated probability." The developer
  corrected this to "estimated impairment probability" since no calibration
  experiment was performed.
- AI initially claimed V2 "found 5 more engineer-confirmed sites." The
  developer verified the actual 8-week results showed no difference and
  corrected the claim.
- AI-generated documentation initially used "realized EUR savings." The
  developer required this to be rewritten as "simulated economic value."

---

## 4. What AI Did Not Do

- AI did not understand the challenge requirements independently.
- AI did not select the official strategy or make architectural decisions.
- AI did not run tests, validation scripts, or Docker verification.
- AI did not determine what constituted acceptable output quality.
- AI-generated code was not committed without local testing and review.
- AI did not author any claim that was not reviewed and verified by the
  developer before inclusion.

---

## 5. Tooling

- **Model**: Google Gemini / Antigravity
- **Use pattern**: Developer-directed pair programming ? the developer
  described what was needed, AI implemented, developer reviewed and tested.
- **Test infrastructure**: pytest (75 tests), validate_submission.py,
  manual CLI verification, Docker health checks.