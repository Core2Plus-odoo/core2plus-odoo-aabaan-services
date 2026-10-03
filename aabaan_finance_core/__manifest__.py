# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Finance Core',
    'version': '19.0.1.3.0',
    'category': 'Accounting',
    'summary': 'Finance dept P1+P2: enforced branch/service analytic segregation and recovery classification',
    'description': """
Implements Priorities 1 and 2 of the Finance Department's Odoo Module
Enhancement Requirements (Aug 2026):

Priority 1 — Branch + Service segregation, enforced
- Every posted customer invoice / vendor bill income or expense line must
  carry an analytic distribution touching both the Emirate (branch) plan and
  the Service Line plan. Posting is blocked with a clear message otherwise
  (fool-proof: no untagged financial transaction can exist). The block covers
  invoices and bills only -- the same business domains native Odoo offers a
  mandatory analytic applicability for. Machine-written journal entries
  (payroll, depreciation, COGS, reconciliation) post and are flagged
  "Untagged for Branch" instead, because blocking them stops a payroll run
  without getting anything tagged.
- Invoices created from contracts inherit the tags automatically where the
  order carries x_emirate_regime / x_service_line.

Priority 2 — Recovery classification
- Every posted customer invoice carries a computed recovery bucket:
  Previous (due before 1 Aug 2026 — the company-history cutoff),
  Current (due this month), Future (due later), plus a manual recovery
  status workflow (Under Recovery, Payment Promised, Partially Paid...).
- Recovery report: filtered, grouped list of open invoices by bucket,
  branch and service with the statuses finance asked for.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['account', 'purchase', 'aabaan_visit_schedule'],
    'data': [
        'data/cron.xml',
        'views/account_move_views.xml',
        'views/management_menus.xml',
        'report/payment_voucher.xml',
    ],
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'application': False,
}
