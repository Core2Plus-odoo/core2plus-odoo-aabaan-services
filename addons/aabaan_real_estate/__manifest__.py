# -*- coding: utf-8 -*-
{
    'name': 'Aabaan Real Estate',
    'version': '19.0.1.1.0',
    'category': 'Sales/CRM',
    'summary': 'Property inventory, matchmaking and branded proposals on Odoo CRM',
    'description': """
Aabaan Real Estate
==================

A real-estate layer on the standard CRM, for Aabaan Real Estate:

- Developers, projects (off-plan and ready) and units, with photos, payment
  plans and live availability.
- A real-estate pipeline (New to Won) for the Aabaan Real Estate team.
- On every lead: what the client wants (budget, area, type, bedrooms),
  lead temperature, portal source, and the units that match.
- A shortlist per lead and a branded proposal PDF in one click.
- Side-by-side comparison of up to four projects.

Leads from portals, Meta and websites come in through standard CRM
(website forms, mail aliases, automation-rule webhooks).
""",
    'author': 'C2P Consultants FZC LLC',
    'website': 'https://c2p.ae',
    'license': 'OPL-1',
    'depends': ['crm', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/crm_data.xml',
        'views/re_project_views.xml',
        'views/re_unit_views.xml',
        'views/re_developer_views.xml',
        'views/crm_lead_views.xml',
        'report/re_reports.xml',
        'report/re_proposal_template.xml',
        'report/re_compare_template.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': ['aabaan_real_estate/static/src/re.scss'],
        'web.report_assets_common': ['aabaan_real_estate/static/src/re_report.scss'],
    },
    'post_init_hook': '_post_init',
    'installable': True,
    'application': True,
}
