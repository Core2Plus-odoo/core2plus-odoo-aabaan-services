# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Field Operations',
    'version': '19.0.1.2.0',
    'category': 'Services/Field Service',
    'summary': 'Guard-railed visit execution: dispatch, start/complete flow, auto follow-ups, SLA escalation',
    'description': """
The execution layer over the Aabaan visit schedule, designed to be fool-proof:

- Preferred technician on the contract; every generated visit is auto-assigned.
- Start Visit is blocked until a technician is assigned and stamps the check-in.
- Complete Visit is blocked until the field report (treatment, chemicals) is
  filled, stamps the check-out, and — when infestation is found — raises the
  unbilled follow-up visit with its SLA automatically (the 3-day rule).
- Cancelling requires a reason; dragging a visit straight to Completed or
  Cancelled on the kanban is intercepted.
- A daily cron escalates SLA breaches and visits a day past plan as activities
  on the technician (once per visit).
- Today's Visits menu under Field Service. (The former Dispatch Board
  menu was retired by the cleanup audit - the Planning Board's kanban
  mode is the same by-technician view; the action survives for saved
  bookmarks.)
- Planning Board: the visit Gantt by technician — drag to reschedule, drag
  between rows to reassign, native per-technician workload bars, red for
  SLA-escalated visits — plus a To Schedule list for visits without a
  planned date (a Gantt can only show what has a date; the gap is made
  visible instead of hidden). Auto-routing is deliberately NOT built: no
  travel-time or geo source exists in this database, and a suggested route
  computed without one would be an invented number.

Rebuilt from the fm_fsm concepts of the previous Aabaan-Services suite,
standard-first on native FSM tasks.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'aabaan_visit_schedule',
    ],
    'data': [
        'data/cron.xml',
        'views/project_task_views.xml',
        'views/planning_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
