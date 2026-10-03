# Aabaan Data Enrichment

Two idempotent sweeps that clean the book without inventing anything.
Both run at install and from the Action menu, fill **only empty fields**,
and post their evidence in the chatter.

## Tag Contract Emirates (`sale.order` → Action menu)

Contracts without `x_emirate_regime` are tagged from, in priority order:
service (delivery) address → customer address → customer name → contract
text. Matching is whole-word (Ajman, Sharjah, Dubai/Deira, Umm Al
Quwain/UAQ, Ras Al Khaimah/RAK, Fujairah, Abu Dhabi); the selection key
is resolved at runtime against the field's actual options. No usable
evidence → left untagged, counted in the summary.

## Enrich Contacts (`res.partner` → Action menu)

Customers (`customer_rank > 0`) get:

- **UAE state + country** — from their own address/name, or from the
  emirate tagged on one of their contracts (source named in the chatter).
- **Industry** — from confident name keywords (cafeteria/restaurant,
  hypermarket, school, hospital/clinic, real estate, contracting,
  hotel …) mapped onto the **native** industry list. Nothing is created;
  no candidate industry found → skipped. This feeds the CEO dashboard's
  "Book by client industry" panel. Each tag names its keyword so a wrong
  guess is one click to fix.

## What is configuration (native Odoo)

- The native industry list (Settings → Technical → Industries) — add
  entries there if a finer split is wanted, then re-run the sweep.
- Corrections: just edit the field on the contract/contact — the sweeps
  never overwrite a set value.
