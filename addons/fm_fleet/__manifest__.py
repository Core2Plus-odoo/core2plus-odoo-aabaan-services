# -*- coding: utf-8 -*-
{
    'name': 'FM Fleet',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Fleet',
    'summary': 'Branch, registration and insurance expiry on Fleet vehicles',
    'description': """
FM Fleet
========

Thin layer on the standard Fleet app for Aaban's service vehicles:

- the FM branch each vehicle works from;
- registration (Mulkiya) and insurance expiry dates.

The Budget Dashboard's Renewals & Compliance section reads them.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['fleet', 'fm_branch'],
    'data': ['views/fleet_vehicle_views.xml'],
    'installable': True,
    'application': False,
}
