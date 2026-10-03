# core2plus-odoo-aabaan-services

Custom Odoo 20 Enterprise addons for the Aabaan Classic Building Cleaning
L.L.C. build (`core2plus-odoo-aabaan.odoo.com`, Odoo.sh, deploys from `main`),
maintained by C2P Consultants FZC LLC.

This repository is the continuation of `Core2Plus-odoo/aabaan` — its full
commit history is preserved here.

| Module | Version | Purpose |
| --- | --- | --- |
| `aabaan_branches` | 20.0.3.0.0 | The emirates as operating branches of one company, with per-branch licence tracking |
| `aabaan_ceo_dashboard` | 20.0.2.2.0 | Seven-tab live executive dashboard: overview, field ops, sales, finance, expenses, cash, AMC renewals |
| `aabaan_client_sites` | 20.0.1.5.0 | Areas on contacts and multi-location clients, wired through visits and contracts |
| `aabaan_contract_cockpit` | 20.0.1.5.0 | Contract command view: term, delivery, money and health KPIs on every confirmed contract |
| `aabaan_data_enrichment` | 20.0.1.1.0 | Auto-tag contract emirates and enrich customer contacts from real evidence |
| `aabaan_field_ops` | 20.0.1.2.0 | Guard-railed visit execution: dispatch, start/complete flow, auto follow-ups, SLA escalation |
| `aabaan_finance_core` | 20.0.1.3.0 | Finance dept P1+P2: enforced branch/service analytic segregation and recovery classification |
| `aabaan_hr_fleet` | 20.0.1.0.0 | Finance P5+P6: native HR/Payroll/Attendance/Leave + Fleet, with vehicle-fine payroll recovery |
| `aabaan_invoice_report` | 20.0.1.1.0 | FTA-compliant Tax Invoice PDF plus a native Document Audit Trail on customer invoices |
| `aabaan_letterhead` | 20.0.1.0.0 | The one shared Aaban letterhead (header, footer, print helpers) for every PDF |
| `aabaan_pricing_guard` | 20.0.1.0.0 | Blocks quotations that would bill nothing, and shows which AED 0 products are safe to archive |
| `aabaan_quotation_report` | 20.0.1.4.0 | Branded quotation/contract PDF in the Aaban Services letterhead style |
| `aabaan_service_contracts` | 20.0.1.3.0 | Multi-site master agreements: per-site SLA lines and a compliance document pack |
| `aabaan_service_reports` | 20.0.1.1.0 | Letterhead service report and certificates printed from the visit |
| `aabaan_templates_library` | 20.0.1.0.0 | Card gallery for quotation templates (approved UI screens) |
| `aabaan_ux` | 20.0.1.0.1 | One deliberate information architecture for the Aabaan menus |
| `aabaan_visit_schedule` | 20.0.1.4.0 | Generate AMC maintenance visit schedules from confirmed contracts |
| `aabaan_website_theme` | 20.0.2.9.0 | Complete booking-first website in the approved Urban Company / Justlife style |

Each module's own `README` documents what is code and what is configuration.
Working rules for this build are in `CLAUDE.md`. The Odoo 19 → 20 migration
and the standard-first audit behind it are in `MIGRATION-20.md`.

Secrets policy: API keys are supplied via environment variables (e.g.
`ODOO_API_KEY`) and are never committed to this repository.
