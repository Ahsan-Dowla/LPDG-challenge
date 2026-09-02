# Problem Understanding

## 1. Problem Statement

LPDG has around 320 gateways that help send meter readings through its radio
network.

When a gateway starts having problems, the issue may not be noticed immediately.
This can eventually lead to incorrect meter readings, manual site visits and
customer problems.

The field team can visit only 15 gateways per week.

The goal of this challenge is to build a system that decides which 15 gateways
should be visited each week, ranks them, and gives a reason for each choice.

---

## 2. What Are We Predicting?

We are predicting the **15 gateways that should be visited for each scored
week**.

There are 8 scored weeks:

- 2026-02-02
- 2026-02-09
- 2026-02-16
- 2026-02-23
- 2026-03-02
- 2026-03-09
- 2026-03-16
- 2026-03-23

So the final output contains:

**15 gateways × 8 weeks = 120 predictions.**

We are not predicting exactly when a gateway will fail. We are ranking gateways
by how much they appear to need attention.

---

## 3. What Is One Observation?

For the main telemetry data, one observation is:

**one gateway at one hour.**

Each telemetry row contains a gateway ID, timestamp and measurements describing
what happened during that hour.

Examples of important measurements are:

- `offline_duration_sec`
- `disconnection_cnt`
- `reboot_cnt`

There are also many other network and gateway health measurements.

---

## 4. What Is One Decision?

One decision is:

> "Should this gateway be included in the 15 gateways we send the field team
> to this week?"

For every scored week, we have to make this decision across the available
gateways and rank the 15 selected gateways from 1 to 15.

The ranking matters because the operations team needs to know which gateways
should be considered the highest priority.

---

## 5. Prediction Timeline

The prediction is made at the start of a Monday.

For example, when making the prediction for the week starting:

`2026-02-02`

we can use information from before that Monday.

The supplied baseline uses:

- The previous 28 days as the historical baseline
- The previous 7 days as the recent period

The same idea is repeated for every scored Monday.

The important point is that the prediction should represent what we could have
known at that point in time.

---

## 6. Available Information

The challenge provides several data sources:

### Telemetry

Hourly information from each gateway.

This includes gateway health, connectivity, reboots, network information and
other measurements.

### Gateway master

Information about the gateways themselves, such as:

- customer
- site type
- region
- hardware model
- antenna type
- firmware
- number of meters installed

### Meter read success

Weekly information about how many meters were expected to be read and how many
were actually read for each gateway.

### Field visits

Historical records of previous site visits, including the reason for the visit
and what the technician found.

### Engineer review

A small set of engineer opinions about gateways, including whether they were
considered `Normal` or `Schlecht`.

These sources may become useful later, especially when we improve on the
baseline.

---

## 7. Information That Must Not Leak

When making a prediction for a particular Monday, we should not use information
that would only have been available after that Monday.

For example, we should not use:

- future telemetry
- future meter-read results
- future field visits
- future engineer reviews

to decide which gateways should have been selected earlier.

This would make the result look better during testing but would not represent
a real-world prediction.

The baseline also follows this rule by taking its 28-day window strictly before
the scored Monday.

---

## 8. What Does "Needs a Visit" Mean?

The challenge does not give us one exact definition.

This is intentionally left open.

A gateway could be considered in need of a visit because of things such as:

- repeated disconnections
- long periods offline
- frequent reboots
- worsening behaviour
- poor meter-read success
- a combination of several warning signs

We need to decide later what signals should matter and how they should affect
the ranking.

For now, I will treat "needs a visit" as:

> A gateway showing enough evidence of current or worsening problems that sending
> an engineer there is more useful than using that visit on another gateway.

This is an initial working definition and may change after exploring the data.

---

## 9. The 15-Visit Constraint

The field team can make exactly 15 visits per week.

This is a hard limit.

Therefore, the system cannot simply flag every gateway that looks problematic.

It must rank the gateways and select the top 15.

This makes the problem a **ranking problem**, rather than simply saying
"problem" or "no problem" for every gateway.

---

## 10. Prediction Output

The final file must be called:

`predictions.csv`

It must contain exactly five columns:

- `week_start`
- `rank`
- `gateway_id`
- `score`
- `reason`

There must be exactly 15 rows for each of the 8 scored weeks.

That gives a total of 120 rows.

The `rank` must be from 1 to 15 within each week, with no repeats.

The `reason` should explain why the gateway was selected and must be 300
characters or fewer.

---

## 11. Baseline Understanding

The supplied baseline uses a simple 3-sigma anomaly detection approach.

For each scored Monday:

1. Take the previous 28 days of telemetry.
2. Calculate the mean and standard deviation for each gateway.
3. Do this for:
   - `offline_duration_sec`
   - `disconnection_cnt`
   - `reboot_cnt`
4. Look at the most recent 7 days.
5. Flag an hour when one of these metrics is more than 3 standard deviations
   above that gateway's own baseline.
6. Count the flagged hours for each gateway.
7. Rank gateways by their number of flagged hours.
8. Select the top 15.

This is a gateway-specific baseline, meaning each gateway is compared against
its own historical behaviour rather than against every gateway in the network.

The baseline does not use machine learning.

It gives us a working starting point that we can understand and compare against
later.

---

## 12. What the Validator Checks

`validate_submission.py` checks whether the output file has the required
structure.

It checks things such as:

- required columns
- no unexpected columns
- exactly 120 rows
- all 8 required weeks
- valid gateway IDs
- numeric scores
- non-empty reasons
- reasons no longer than 300 characters
- exactly 15 rows per week
- ranks 1 to 15
- no duplicate gateways within a week

Passing the validator means the file has the correct format.

It does **not** mean that our actual gateway choices are good.

---

## 13. What the Challenge Deliberately Leaves Unspecified

The challenge does not tell us exactly:

- what "needs a visit" means
- how early we should detect a problem
- how many false alarms are acceptable
- which gateway metric is most important
- how different signals should be combined

These are part of the engineering judgement we are expected to demonstrate.

The challenge also gives two different costs:

- €380 when a visit turns out to be unnecessary
- €600 for leaving a broken gateway for another week

The €600 cost can happen again every week while the gateway remains broken.

This means the ranking should eventually consider not just whether something
looks unusual, but also the operational cost of getting the decision wrong.

---

## 14. Initial Questions / Assumptions

Before improving the baseline, I want to answer these questions by exploring
the data:

1. Which telemetry signals are actually related to poor gateway behaviour?

2. Are some gateways naturally more noisy than others?

3. Does a recent increase in failures matter more than a consistently high
   value?

4. Does poor gateway health actually lead to poor meter-read success?

5. What do previous field visits tell us?

6. Does the number of meters behind a gateway change how important a visit is?

7. Are there missing or unreliable telemetry periods?

8. Can we detect a problem before it becomes a major failure?

9. How often would the baseline select gateways that appear healthy?

10. How often would it miss gateways that later show evidence of problems?

These questions will guide the next stage of the project.

For now, the main goal is not to build the perfect ranking system.

The first goal is to understand the data and reproduce the baseline correctly.