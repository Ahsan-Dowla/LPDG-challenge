# AI Usage Transparency

This document explains how AI tools were used during the development of this
project for the **LPDG Innovation Hub Selection Challenge 2026**.

AI was used as an engineering assistant for implementation, debugging,
testing, refactoring, and documentation. The overall approach, engineering
decisions, validation, and final submission decisions remained developer-led.

---

## AI Tools Used

The project used:

- **Google Antigravity / Gemini models**
  - Code implementation
  - Refactoring
  - Debugging
  - Test generation
  - Documentation assistance

- **GitHub Copilot**
  - Implementation assistance
  - Test generation and debugging
  - CI workflow development
  - Repository cleanup and refactoring

AI-generated output was reviewed and validated before being incorporated
into the project.

---

## How AI Was Used

### Code Implementation

AI assisted with implementing and refining:

- Data loading and validation utilities
- Gateway eligibility logic
- The V1 ranking strategy
- The V2 probabilistic challenger
- FastAPI routes and schemas
- Error handling
- The `src/lpdg/` package architecture
- Compatibility layers
- CLI execution
- Docker configuration
- GitHub Actions CI

The ranking methodology and major architectural decisions were defined by the
developer before implementation assistance was given to AI.

---

### Testing and Debugging

AI was used to:

- Generate unit and integration tests.
- Diagnose failures from test output and tracebacks.
- Add regression tests for identified bugs.
- Strengthen frozen-output comparisons.
- Test API behaviour and error handling.
- Help separate challenge-data-dependent tests from public CI tests.

All tests were executed and reviewed as part of the development process.

---

### Documentation

AI assisted with drafting and refining:

- `README.md`
- `DECISIONS.md`
- `docs/architecture.md`
- `docs/methodology.md`
- `docs/runbook.md`
- `docs/limitations.md`
- `docs/api.md`
- `AI-USAGE.md`

Documentation claims were reviewed against the actual implementation and
results before being retained.

---

## Things AI Got Wrong and I Helped

### 1. Persistence Coverage Bug

An early implementation calculated persistence as:

```text
persistence = problem_hours / coverage_hours
```

This created a misleading result when telemetry coverage was sparse.

For example:

```text
20 observed hours
20 impaired hours
→ persistence = 1.0

168 observed hours
168 impaired hours
→ persistence = 1.0
```

These two cases should not be treated as equally strong evidence. The first
gateway has only 20 hours of observed telemetry, while the second has a full
168-hour observation window.

I identified this by inspecting the generated rankings and comparing gateways
with different levels of telemetry coverage.

The calculation was changed to:

```text
persistence = problem_hours / max(coverage_hours, 168)
```

I then added a dedicated regression test to ensure that sparse telemetry cannot
receive the same persistence treatment as a gateway with a complete
168-hour observation window.

---

### 2. API Behaviour

An early API implementation focused primarily on serving already-generated
prediction results.

This did not fully satisfy the operational requirement that the system should
also be able to run the ranking process again when requested.

I helped revise the API to clearly separate:

- retrieving predictions for a week;
- explaining why a gateway received its ranking; and
- triggering a fresh ranking run.

I also helped add controlled handling for unknown gateway IDs, invalid week
values, missing challenge data, and invalid requests.

The final API was kept independent from the internal ranking strategy so that
the ranking implementation can be changed without rewriting the API layer.

---

### 3. CI and Private Dataset Dependency

An early CI implementation assumed that the challenge dataset would be
available inside GitHub Actions.

This was incorrect for the public repository because the challenge dataset is
private and should not be committed to Git.

I helped redesign the CI workflow so that public CI runs tests that do not
require the private challenge dataset, using synthetic fixtures where
appropriate.

Challenge-data-dependent tests remain available for the local development
environment.

The resulting separation is:

```text
Public CI
    ↓
Dataset-independent tests
    ↓
Frozen-output / structural checks

Local challenge environment
    ↓
Private challenge dataset
    ↓
Full ranking + challenge-data tests
```

This allowed the public repository to remain testable without exposing or
requiring the challenge dataset.

---

### 4. Regression Test Coverage

An early regression test did not verify the complete prediction output.

I helped strengthen it to compare the complete submission contract:

```text
week_start
rank
gateway_id
score
reason
```

The regression suite was also strengthened around frozen outputs and temporal
leakage.

This was important because a refactor could otherwise pass basic tests while
silently changing the actual submitted rankings or explanations.

---

### 5. Architecture Coupling

During the architecture refactor, some AI-generated implementation coupled
ranking logic too closely to the API and service layer.

I helped separate these responsibilities by introducing a ranking strategy
interface and a dedicated ranking service.

The resulting structure is conceptually:

```text
API
 │
 ▼
Ranking Service
 │
 ├── V1 Ranker
 └── V2 Ranker
```

This allows the ranking strategy to be replaced without changing the API
contract or the surrounding application logic.

---

### 6. Documentation Claims

Some AI-generated documentation initially described experimental results more
strongly than the evidence supported.

For example, **"calibrated probability"** was too strong because no formal
calibration experiment had been performed.

I corrected this to **"estimated impairment probability"**.

Similarly, an early description referred to **economic savings** in a way that
could be interpreted as realized savings.

I corrected this to **"simulated economic value"**, because the result came
from historical backtesting and assumed cost parameters rather than actual
operational savings.

---

### 7. Test Environment Assumptions

Some generated tests initially depended on specific challenge gateway IDs or
the private dataset.

Those assumptions caused failures when the tests were executed in the public
repository environment.

I helped reorganize the tests to use synthetic fixtures for
dataset-independent tests while keeping challenge-data-dependent verification
separate.

The final local test suite contains:

```text
82 passed
```

---

These examples reinforced an important development principle:

> **AI-generated code was treated as a starting point, not as verified
> engineering truth.**

Each significant change was reviewed against the challenge requirements,
actual system behaviour, tests, and validation results before being accepted.

---

## Developer Responsibility

The developer remained responsible for:

- Understanding the challenge brief and data dictionary.
- Deciding what "needs a visit" should mean operationally.
- Selecting the evidence-based V1 approach.
- Defining the ranking signals and methodology.
- Identifying and fixing the persistence coverage issue.
- Deciding to retain V2 as a challenger rather than automatically replacing
  V1.
- Reviewing AI-generated implementation.
- Running tests and validation.
- Verifying prediction outputs.
- Testing the API and Docker deployment.
- Ensuring the public repository does not contain the private challenge data.
- Making the final architectural and submission decisions.

AI suggestions were treated as implementation proposals, not as verified
engineering decisions.

---

## Final Verification

The final implementation was verified using:

- **82 local pytest tests**
- `validate_submission.py`
- Frozen prediction-output regression checks
- CLI execution through `main.py`
- FastAPI endpoint testing
- Docker health checks
- GitHub Actions CI

The final prediction file was checked using the provided submission validator
before submission.

The challenge dataset is private and is intentionally excluded from the public
repository.

---

## Development Workflow

```text
Challenge requirements
        │
        ▼
Developer defines approach
        │
        ▼
AI-assisted implementation
        │
        ▼
Developer review
        │
        ▼
Tests + validation
        │
        ▼
Investigate failures
        │
        ▼
Correct implementation
        │
        ▼
Final developer decision
```

**AI accelerated implementation and iteration; the developer remained
responsible for the final technical decisions and validation.**
