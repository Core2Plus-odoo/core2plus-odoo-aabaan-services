# -*- coding: utf-8 -*-
{
    "name": "FM Customer Portal",
    "version": "19.0.1.1.0",
    "category": "Facility Management",
    "summary": "Customer portal: jobs, certificates and service reports, service requests",
    "description": """
FM Platform — Customer Portal
=============================
What the customer sees under /my, on top of what Odoo already gives them.

Already standard, configured rather than coded:

* invoices and online payment (``account_payment``, needs a payment provider);
* quotations approved with an e-signature (``sale``);
* the portal branded by the website theme (``aabaan_website_theme``).

Added here:

* **Jobs** — the customer's current and upcoming visits. Odoo only shows a
  portal user the tasks they follow, and the customer follows almost none
  of theirs, so a portal rule opens the FSM visits of their own company.
* **Certificates & Reports** — compliance certificates for the assets on
  their contracts, and the service report of every completed visit.
* **Service Request** — a form that raises a CRM lead against the customer,
  into the same Sales → Accounts → Operations handover as a website booking.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "portal",
        "crm",
        "sale",
        "account_payment",
        "industry_fsm_report",
        "fm_contract",
        "fm_fsm",
        "fm_compliance",
        "fm_documents",
    ],
    "data": [
        "security/portal_rules.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "fm_portal/static/src/scss/portal.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
