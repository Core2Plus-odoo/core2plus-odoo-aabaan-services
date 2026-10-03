# Aabaan Visit Schedule Generator (`aabaan_visit_schedule`)

The one genuine custom module of the Aabaan build. `sale_subscription` drives
*billing* recurrence; this module drives *visit* recurrence — for Aabaan these
are different things (a contract billed annually may carry 24 visits, and Dubai
F&B cadence is set by regulation, not by the billing cycle).

## What it does

**Routine schedule generation** — on confirmation of a sale order that carries
a contracted visit count (or via the **Generate Visits** button on the order):

- Reads `x_visit_count`, the contract term, `x_service_line`,
  `x_emirate_regime`, `x_site_address` and the customer from the order.
- Batch-creates `project.task` records in the Field Service project, spaced
  evenly across the term (term days ÷ visit count), stage **Scheduled**,
  `x_visit_type='routine'`, `x_visit_no` numbered 1..n.
- Skips non-working days using the company `resource.calendar` (weekly
  attendances + calendar-wide leaves), rolling forward to the next working day
  (backward at the very end of the term).
- The single task auto-created by `service_tracking='task_global_project'` on
  confirmation is absorbed as a numbered visit, not duplicated.
- **Dubai LO 11 (2003):** when `x_emirate_regime` is Dubai and **F&B Premises**
  is ticked on the order, the schedule runs at 2 visits per month; the higher
  of that and `x_visit_count` wins.

**Idempotent regeneration** — safe to re-run at any time, including after a
mid-term contract change:

- Visits at **In Progress or beyond** (incl. Cancelled) are never rewritten,
  renumbered or deleted; their visit numbers stay reserved (a cancelled
  visit's slot is refilled).
- **Scheduled/Assigned** visits are re-planned in place; missing visits are
  created; surplus open visits are removed.
- Every run posts a summary to the order's chatter: counts kept / re-planned /
  created / removed, the planned dates, and any assumption made.

**Unbilled follow-up & complaint visits** — **Raise Follow-up** / **Raise
Complaint** buttons on the confirmed order *and* on any visit task linked to a
contract:

- Follow-up: planned and SLA-stamped at `x_followup_days` (default 3) from
  today, per the 3-day follow-up rule.
- Complaint: planned same day; `x_sla_due` stamped from the contract's
  `x_complaint_sla` (same day / 24h / 48h).
- Both are linked to the order for traceability but carry **no**
  `sale_line_id`, so they can never be billed under the AMC — keeping job
  costing able to separate billed routine visits from unbilled ones.

## Field contract — read before changing the Studio fields

The `x_*` fields on `sale.order` (`x_visit_count`, `x_service_line`,
`x_emirate_regime`, `x_complaint_sla`, `x_followup_days`, `x_site_address`)
and `project.task` (`x_visit_type`, `x_visit_no`, `x_sla_due`,
`x_service_line`, `x_emirate`) are **manual fields defined in the database**,
not in this module. The module deliberately does not redefine them: doing so
blind could corrupt the live definitions. Instead it resolves them at runtime:

- Missing field → the value is skipped, generation still works.
- Selection keys are matched by substring on key *and* label (e.g. `follow`
  matches `followup`, `follow_up` or `Follow-up`), so renaming a key degrades
  gracefully rather than crashing.
- `x_sla_due` and the task date fields are written as date or datetime
  according to their actual type.

Expectations that must hold for full functionality: `x_visit_count` and
`x_visit_no` are integers; `x_visit_type` contains keys matching
routine/follow/complaint; the Dubai regime key contains "dubai"; the FSM
stages include names "Scheduled" and "Assigned" (matched case-insensitively).

The only fields this module owns are `is_fnb_premises` and the computed
`visit_task_count` on `sale.order`.

## Assumptions (flagged in chatter when applied)

- **No end date on the order** → 12-month term is assumed (contract
  frequencies are quoted per year, e.g. "Yearly 12 Times").
- **Dubai F&B months** are computed from the term length (~30.44 days/month).
- **Mid-term regeneration keeps contract-anchored dates**: an unfilled slot
  whose planned date is already past stays in the past — an overdue Scheduled
  visit is a truthful record of a missed visit, to be rescheduled manually.
- **Working days follow the company calendar.** Note: the build handoff's
  acceptance test says "no Friday or Saturday", but the configured company
  calendar is Mon–Fri (Sat/Sun off, the current UAE working week). The
  calendar is the source of truth; adjust the calendar if Fridays must be
  excluded.

## Tests

`tests/test_visit_schedule.py` covers the handoff acceptance test (12-visit
Ajman contract from 1 Sep 2026), idempotency, mid-term changes with started
visits, Dubai F&B cadence, and follow-up/complaint SLA stamping. A fresh test
database lacks the manual fields, so the test setup recreates them via
`ir.model.fields` exactly as the production build did.

Run: `odoo-bin -d <db> -i aabaan_visit_schedule --test-tags /aabaan_visit_schedule --stop-after-init`
