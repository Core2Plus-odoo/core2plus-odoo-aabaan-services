# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Branches',
    'version': '19.0.3.0.0',
    'post_init_hook': '_post_init_hook',
    'category': 'Hidden/Tools',
    'summary': 'The emirates as operating branches of one company, with per-branch licence tracking',
    'description': """
One company, several branches. The emirate presences — Ajman (head
office), Dubai and Sharjah — are run as **branches of the single Aaban
company**, not as separate companies in Odoo.

The branch dimension is the **Emirate analytic plan**, which already
exists in the production database and which ``aabaan_finance_core``
autofills and enforces on every posting. This module does not invent a
second dimension alongside it; it annotates that one:

- Each Emirate analytic account carries its own **Trade Licence No.** and
  **expiry**, taken from the licence documents:
  Ajman 103074 (08-Jan-2027), Dubai 989256 (13-Oct-2026),
  Sharjah 908692 (01-Jul-2026). The letterhead's old "109374" appears on
  none of the licences and is corrected wherever it was used.
- A daily check raises one renewal activity 60 days ahead, for the company
  licence and for every branch licence.
- Contracts (``sale.order``) get a **Branch** field pointing at one of those
  analytic accounts, groupable and searchable. When set, it drives the
  Emirate analytic tag on the invoices raised from the contract instead of
  matching the ``x_emirate_regime`` label against account names.

Head-office contact data is corrected from the letterhead where Odoo's
demo placeholders were still in place.

**Migrating from separate companies.** Earlier versions of this module
split Dubai and Sharjah into standalone companies. This version stops
maintaining that split, but it does not undo it: Odoo cannot move journal
entries between companies, so consolidating existing books is a manual
accounting exercise. See README.md.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['base', 'mail', 'account', 'sale'],
    'data': [
        'data/cron.xml',
        'views/res_company_views.xml',
        'views/branch_views.xml',
    ],
    'installable': True,
    'application': False,
}
