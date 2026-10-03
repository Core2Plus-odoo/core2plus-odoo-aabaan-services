# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Invoice Report',
    'version': '19.0.1.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'FTA-compliant Tax Invoice PDF plus a native Document Audit Trail on customer invoices',
    'description': """
Adds the Tax Invoice layout from the approved UI reference — every mandatory
FTA field (Federal Decree-Law No. 8 of 2017 / Cabinet Decision 52), on the
Aaban letterhead:

- The words "Tax Invoice" (or "Tax Credit Note" for a credit note) shown
  clearly, supplier name/address/TRN/trade licence, recipient name/address
  and TRN when registered, a sequential invoice number, the invoice date,
  the date of supply when it differs (native delivery_date, only if set),
  payment due date, per-line description/qty/unit price/discount/VAT rate,
  the gross and VAT amounts, and the grand total.
- A reverse-charge notice, shown only when the invoice's own fiscal
  position is actually configured for it — never asserted by default.
- A Payment Details block, shown only if the issuing company has a real
  bank account on file — never invented.

New report action ("Tax Invoice (Aaban)") on customer invoices/credit
notes only, added via the standard Print-menu binding — the native
invoice print action is untouched.

Document Audit Trail: a new tab on the invoice form built entirely from
data the system already has — created/posted timestamps, whether it was
actually emailed (native mail.mail records), real payments reconciled
against it (account.partial.reconcile), and any credit notes issued
against it. Nothing here is estimated; a milestone that hasn't happened
yet simply doesn't appear.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['account', 'aabaan_letterhead'],
    'data': [
        'report/invoice_report.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
