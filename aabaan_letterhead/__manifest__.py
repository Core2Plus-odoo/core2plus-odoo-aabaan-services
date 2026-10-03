# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Letterhead',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': 'The one shared Aaban letterhead (header, footer, print helpers) for every PDF',
    'description': """
Cleanup-audit consolidation: the letterhead header/footer markup existed
in three copies (quotation report, service documents, tax invoice), and
two print helpers (product-code stripping, amount in words) existed in
two. One divergence per copy per edit was inevitable.

This module now owns the single canonical letterhead:

- ``aabaan_letterhead.header`` / ``aabaan_letterhead.footer`` QWeb
  templates — the flat two-tone band design (the CSS-triangle version was
  retired here too: triangles render unreliably in wkhtmltopdf, which is
  why the quotation abandoned them first). Callers set ``company`` in
  scope and t-call.
- ``tools.line_desc`` / ``tools.amount_in_words`` — the shared print
  helpers, imported by the report modules' thin model wrappers.

No visual change to quotations or tax invoices; service documents gain
the flat band (previously still triangles) and the full offices footer —
an intended alignment, not an accident.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['web'],
    'data': [
        'report/letterhead.xml',
    ],
    'installable': True,
    'application': False,
}
