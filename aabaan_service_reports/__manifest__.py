# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Service Documents',
    'version': '19.0.1.1.0',
    'category': 'Services/Field Service',
    'summary': 'Letterhead service report and certificates printed from the visit',
    'description': """
The documents every visit promises, printed from the visit itself (Print
menu on the Field Service task), in the Aabaan letterhead style:

- Service Report — visit details, check-in/out, findings, treatment and
  chemicals from the field report, follow-up raised, signatures. Shows a
  DRAFT banner until the visit is completed.
- Water-Tank Cleaning & Disinfection Certificate — completed tank jobs
  only; next-clean guidance (twice-yearly cadence).
- Anti-Termite Warranty Certificate — completed termite jobs only;
  10-year warranty with the computed end date, free re-treatment clause
  per the signed agreement.

Fool-proof: certificates refuse to print for uncompleted visits or for
the wrong service kind (checked against the contract's service line, its
lines and the visit name) — with a reason, not a wrong document.
All values resolve at runtime; absent manual x_* fields degrade to empty.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['aabaan_field_ops', 'aabaan_quotation_report', 'aabaan_letterhead'],
    'data': [
        'report/service_documents.xml',
    ],
    'installable': True,
    'application': False,
}
