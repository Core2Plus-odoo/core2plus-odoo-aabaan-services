# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Contract Cockpit',
    'version': '19.0.1.5.0',
    'category': 'Sales/Sales',
    'summary': 'Contract command view: term, delivery, money and health KPIs on every confirmed contract',
    'description': """
The contract command view from the approved UI screens, standard-first: no new
models, no custom JS — computed KPIs on the sale order, shown on a Contract
Cockpit tab and a Contracts register menu.

- Term & renewal: days to end-of-term with an overdue/window/healthy state.
- Delivery: visits planned / completed / overdue and SLA escalations, from the
  Field Service tasks the visit scheduler generates and field ops stamps.
- Money: invoiced, paid and outstanding totals from posted invoices.
- Contract health (0-10): derived only from real signals — payment
  timeliness, delivery progress on due visits, and SLA cleanliness — with a
  note explaining which components were available. No invented numbers.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['aabaan_field_ops'],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
