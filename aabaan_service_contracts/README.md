# Aabaan Service Contracts

The "Sites & Compliance" screen from the approved UI reference — a master
agreement covering several sites, each with its own SLA, plus a compliance
document pack. Standard-first: no separate "Contracts app," this extends
the existing contract record (`sale.order`, already the Contract Cockpit).

## What is code (this module)

- **Sites & SLA** (`aabaan.contract.site`, one2many on the order): site,
  service tags, frequency, SLA response target, **SLA Uptime YTD** (real —
  computed from Field Service visit history via `aabaan_field_ops`'s
  `sla_escalated` flag, 0 until visits exist, never estimated), and
  **Site Value** (sum of the order's own lines tagged to that site via
  the new `site_id` column on Order Lines — not a fabricated
  monthly-billing conversion, since cadence varies by contract).
- Contract-level rollup: site count, **visit-weighted average uptime**
  (a site with more visit history counts more — not a naive average).
- **Compliance Documents** (`aabaan.contract.document`): typed pack
  (Master Agreement / Insurance / ISO / MSDS / Staff Roster / Other) with
  a file, an optional expiry date, and a computed status
  (valid / expiring soon / expired / no expiry). A daily cron raises one
  renewal activity per expiring document, 60 days out, no duplicates —
  the exact pattern already shipped for trade-licence expiry in
  `aabaan_branches`.
- Renewal terms recorded as facts: notice period (days, defaults to 90 —
  the same renewal window the Contract Cockpit already uses elsewhere,
  editable, confirm against the signed agreement) and an indexation
  clause (None / CPI-linked with a cap %).

## What is deliberately NOT built

The reference mockup shows an "indicative uplift" AED amount computed
from a CPI rate (e.g. "+3.4% → AED 617,799"). This database has no live
UAE CPI rate source. Rather than invent one, the clause and cap are
recorded as facts and the uplift amount is left for a future integration
once a real rate feed exists — per the standing "no invented numbers" rule.

## What is configuration (native Odoo)

- Service Tags (Sales → Service Tags) — create the tags your team uses
  per site (Pest Control, Cleaning, AC Duct, …).
- Uploading documents and setting sites is done directly on the
  contract's **Sites & Compliance** tab.
