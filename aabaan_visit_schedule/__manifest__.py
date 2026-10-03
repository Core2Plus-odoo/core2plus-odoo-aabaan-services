# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Visit Schedule Generator',
    'version': '19.0.1.4.0',
    'category': 'Services/Field Service',
    'summary': 'Generate AMC maintenance visit schedules from confirmed contracts',
    'description': """
Generates the Field Service visit schedule for Aabaan Classic Building
Cleaning L.L.C. AMC contracts.

- On confirmation of a sale order carrying a contracted visit count, routine
  visits are batch-created in the Field Service project, spaced evenly across
  the contract term, skipping non-working days of the company working calendar.
- Regeneration is idempotent: visits at In Progress or beyond are never
  duplicated, renumbered or deleted; only Scheduled/Assigned visits are
  re-planned.
- Dubai Municipality Local Order No. 11 (2003): food & beverage premises under
  the Dubai regime are scheduled at 2 visits per month regardless of a lower
  contracted count.
- Manual actions raise unbilled follow-up and complaint visits against the
  contract, stamping the SLA deadline from the contract's complaint SLA
  (same day / 24h / 48h) or follow-up interval.

See the module README for the field contract and design notes.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'industry_fsm_sale',
    ],
    'data': [
        'views/sale_order_views.xml',
        'views/project_task_views.xml',
        'views/maintenance_calendar.xml',
    ],
    'installable': True,
    'application': False,
}
