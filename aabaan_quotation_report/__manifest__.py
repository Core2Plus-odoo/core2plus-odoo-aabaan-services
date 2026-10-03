# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Quotation Report',
    'version': '19.0.1.4.0',
    'category': 'Sales/Sales',
    'summary': 'Branded quotation/contract PDF in the Aaban Services letterhead style',
    'description': """
Replaces the standard sale quotation PDF with the Aaban Services letterhead
layout, matching the company's signed contract documents:

- Black angular header band with orange slash and the company logo + tagline.
- Customer name and Ref#/Date block, Subject line, First Party / Second Party
  intro, and the contract Articles (taken from the order's terms, which the
  quotation templates carry from the signed agreements).
- Orange line-items table (# / Description / Unit / Rate / Grand Total).
- VAT 5% breakdown, grand total and amount in words.
- Two-column signature blocks and the Head Office / Branch Offices footer with
  TRN and trade licence for compliance.

The default "Quotation / Order" report action is redirected to this layout, so
printing, email and the customer portal all use it. To revert, point
sale.action_report_saleorder's report_name back to sale.report_saleorder.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'aabaan_visit_schedule',
        'aabaan_letterhead',
    ],
    'data': [
        'report/quotation_report.xml',
    ],
    'installable': True,
    'application': False,
}
