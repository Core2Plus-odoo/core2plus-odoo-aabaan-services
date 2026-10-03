# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Pricing Guard',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Blocks quotations that would bill nothing, and shows which AED 0 products are safe to archive',
    'description': """
Closes the underbilling hole flagged in the business model review: the
catalogue carries legacy duplicate SKUs priced at AED 0 (AAB-PEST,
AAB-WATER, AAB-ANTI, AAB-DEEP, AAB-SOFA, AAB-ATTESTAION, AAB-LAB) alongside
the correctly priced products. Picking the wrong one silently bills
nothing, with no system guardrail.

- Confirmation gate: a quotation cannot be confirmed while any product
  line would bill nothing. The message names the offending lines and
  states both ways out — fix the price, or mark the line intentionally
  free. Measured on the line subtotal, so a 100% discount is caught as
  well as an AED 0 product; both underbill identically.
- Deliberately free work stays one tick away (free follow-ups, call-outs
  covered by the contract entitlement, agreed goodwill) but requires a
  written reason, so ticking the box is an audit trail rather than a
  silent bypass.
- Zero-Priced Products review screen: every sellable AED 0 product with
  how many order lines use it, and how many of those are confirmed. Unused
  products are safe to archive; products already on confirmed orders need
  their price fixed instead. The archiving decision is then made on
  evidence rather than assumption.

Archiving the duplicates is configuration, done from that screen; this
module makes the wrong path impossible whether or not they are archived.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['sale_management'],
    'data': [
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
}
