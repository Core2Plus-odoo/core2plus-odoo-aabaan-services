# -*- coding: utf-8 -*-
{
    'name': 'FM Command Centre',
    'version': '19.0.3.3.0',
    'category': 'Reporting',
    'summary': 'CEO Dashboard — AMC contracts and cash sales side by side, '
               'per branch, live from Odoo',
    'description': """
CEO Dashboard — "Two Businesses, One View"
==========================================

One monthly page for the CEO, laid out after the client's own dashboard
PDF, every figure read live from the database:

1. AMC vs Cash — revenue per stream against target, visits, jobs,
   receivables, 12-month trend.
2. AMC Department — active contracts, new contracts, renewals, contracts
   due in the next 60 days, per-branch table.
3. Cash Sales — jobs, average job value, how clients paid, cash controls.
4. Branch Scorecard — both streams per branch against target.
5. Revenue by Service — every service split AMC / cash.
6. Services by Emirate — service × branch matrix.
7. Credit Recovery — receivables by stream, SOP ageing buckets, key
   accounts.
8. Sales Team — deals per salesperson against target.
9. Expenses & Margin — spend by account, net profit and margin.
10. Cash & Bank — balances, year-to-date flows, recent movements.

Revenue stream (AMC / Cash), service and branch are stored on invoices,
contracts and visits by derivation and stay editable. Targets live on the
branch (AMC + cash), the salesperson (deals) and the company (margin),
under Command Centre → Configuration. The page prints to PDF.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'project',
        'sale_management',
        'account',
        'crm',
        'hr',
        'fm_branch',
    ],
    'data': [
        'security/command_centre_security.xml',
        'security/ir.model.access.csv',
        'views/config_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fm_command_centre/static/src/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
