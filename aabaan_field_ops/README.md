# Aabaan Field Operations (`aabaan_field_ops`)

The guard-railed execution layer over `aabaan_visit_schedule` — rebuilt from
the `fm_fsm` concepts of the previous Aabaan-Services suite, standard-first on
native FSM tasks. "Fool-proof" here means: **the easy path is the correct
path, and the wrong path is blocked with a reason.**

## Dispatch

- **Preferred Technician** on the contract (sale order) — auto-assigned to
  every generated visit, routine and ad-hoc alike.
- **Field Service → Today's Visits** — the day list, grouped by technician.
- **Field Service → Dispatch Board** — open visits grouped by technician;
  the *Unassigned* filter catches visits without an owner.

## Guard-railed visit flow (buttons on the visit)

| Action | Blocked until | What it does |
|---|---|---|
| **Start Visit** | a technician is assigned | stamps Check-in, stage → In Progress |
| **Complete Visit** | started + *Treatment Carried Out* filled | stamps Check-out; if *Infestation Found* → auto-raises the unbilled follow-up (3-day rule) and stage → Follow-up Required, else → Completed |
| **Cancel Visit** | a cancellation reason is written | stage → Cancelled, reason logged to chatter |

Dragging a visit straight to Completed / In Progress / Cancelled on the
kanban (or a mass stage edit) is intercepted with a message pointing to the
right button. Guards apply only to typed Aabaan visits — imports and ordinary
tasks are untouched. Time on site is computed from the stamps.

## Escalation (daily cron)

Open visits past their SLA deadline (`x_sla_due`) or a day past their planned
start with no check-in get a To-Do activity on the technician (or project
manager) — once per visit, flagged `sla_escalated` and filterable.

## Field report

The *Field Report* tab on the visit holds findings (infestation flag,
treatment, chemicals/materials — what the municipality return needs),
check-in/out times, and the linked follow-up.

## What was deliberately NOT rebuilt (per the previous suite's own rule)

Worksheets (Studio-built, Priority 2), materials billing
(`industry_fsm_sale`/`industry_fsm_stock`), and timesheet billing are native
Odoo — configure, don't re-code.

## Planning Board (the Gantt from the approved UI reference)

Field Service → **Planning Board**: every scheduled visit on its
technician's row. Standard-first — the impressive parts of the mockup are
**native Enterprise Gantt behaviour**, not custom code:

- drag a visit to reschedule it, drag it between rows to reassign it;
- the Unassigned row catches visits without an owner;
- day / week / month scales;
- the bar on each technician row is their workload for the visible period,
  computed by Odoo from real working calendars.

What this module adds is only the tuning: SLA-escalated visits render
red (`sla_escalated`), the popover carries customer/contract/check-in,
and the default filter shows open visits.

**To Schedule** is the honest companion lane: a Gantt can only show what
has a date, so visits without a planned date would silently not appear.
They land in this list instead — the dispatcher's backlog, visible rather
than hidden.

**Deliberately NOT built: auto-routing.** The mockup's suggested-route
engine needs travel-time or geo data, and this database has neither. A
route computed without a real distance source would be an invented
number; the workload bars and the map-free Gantt are what the data can
honestly support today.
