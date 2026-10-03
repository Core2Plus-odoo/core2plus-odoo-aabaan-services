# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Executive Command Centre',
    'version': '19.0.2.2.0',
    'category': 'Reporting',
    'summary': 'Seven-tab live executive dashboard: overview, field ops, sales, finance, expenses, cash, AMC renewals',
    'description': """
The Executive Command Centre for Aaban Classic Building Cleaning — five
tabs, each loaded on demand, every figure drillable to the records behind
it, and a period selector that compares each window against the previous
window of the same length.

- Executive Overview — contracted book, quotations, pipeline, receivables,
  customers; period block with like-for-like deltas; 12-month invoiced
  revenue and cash-collected trends; top customers by share of book.
- Field Operations — visits completed, first-time-fix rate (completed
  without a follow-up being raised), SLA-clean rate, average time on site
  from real check-in/check-out stamps; live attention cards; technicians by
  visits and hours; open visits by stage, type and emirate.
- Sales & CRM — contracts signed with delta, open quotations, quotation
  conversion, open pipeline by stage, win rate over decided leads, lead
  sources, lost reasons, contract size mix.
- Finance — receivables, invoiced, collected, collection ratio, days sales
  outstanding (inputs shown on screen), five-band ageing from the due date,
  recovery classification, invoiced-against-collected, top debtors.
- Expenses & Margin — total spend, invoiced, what is left after it and the
  margin, payroll share; invoiced against spent over 12 months; where the
  money went, by expense account; cost by emirate off the Emirate analytic
  dimension. Spend is read from the accounts it was booked to, so payroll
  journals count alongside vendor bills.
- Cash & Bank — balance across the bank and cash accounts, money in, money
  out, net movement, the 12-month flow, balance per account and recent
  movements. Not split by emirate: a bank account belongs to the company,
  not a branch.
- AMC & Renewals — renewal buckets and 12-month timeline, contracts at risk
  with the evidence stated per contract, compliance documents expiring.

Design rules held throughout: aggregation batched via _read_group; the
manual x_* fields and sibling-module fields resolved at runtime so a
missing field collapses its own section instead of raising; and no figure
estimated — where a number cannot be derived from real records it is left
out and the reason is stated on screen. Menu: Command Centre (sales
managers).
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'aabaan_visit_schedule',
        'sale_subscription',
        'crm',
    ],
    'data': [
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aabaan_ceo_dashboard/static/src/**/*',
        ],
    },
    'installable': True,
    'application': True,
}
