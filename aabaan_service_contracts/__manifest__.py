# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Service Contracts',
    'version': '19.0.1.3.0',
    'category': 'Sales/Sales',
    'summary': 'Multi-site master agreements: per-site SLA lines and a compliance document pack',
    'description': """
The Sites & Compliance screen from the approved UI reference, standard-first:
no separate "Contracts app" — this extends the existing contract record
(sale.order, already the Contract Cockpit) with the two things it doesn't
carry natively:

- Sites & SLA: one line per site under a master agreement — services,
  frequency, SLA response target, visit-derived SLA uptime YTD, and the
  site's share of the contract value (from order lines tagged to it via
  a new Site column). Uptime is computed from real Field Service visit
  history (aabaan_field_ops) — never estimated.
- Compliance Documents: a typed document pack (Master Agreement,
  Insurance, ISO/quality certificate, MSDS pack, staff roster, other)
  with per-document expiry tracking and a daily renewal-reminder cron,
  mirroring the trade-licence-expiry pattern in aabaan_branches.

Renewal notice period and CPI indexation clause are recorded as contract
facts (editable, confirm against the signed agreement) — the indicative
uplift AMOUNT shown in the reference mockup is deliberately NOT computed:
this database has no live UAE CPI rate source, and estimating one would
be an invented number.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['aabaan_contract_cockpit', 'aabaan_client_sites'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/contract_site_views.xml',
        'views/contract_document_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
