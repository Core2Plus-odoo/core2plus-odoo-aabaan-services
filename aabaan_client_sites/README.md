# Aabaan Client Sites & Areas

One client, many service locations — carried the native way, with the
missing UAE "area" concept added on top.

## What is configuration (native Odoo — the backbone)

- **Each location is a child contact** of the client: open the client →
  Contacts & Addresses → add a **Delivery Address** per site (the
  Locations smart button does the same with sensible defaults).
- **Each contract picks its site** in the native Delivery Address field —
  visits generated for the contract carry that site, and the enrichment
  sweep reads it first when tagging emirates.

## What is code (this module)

- `Area / District` on every contact (indexed char, shown in the address
  block and contacts list).
- A **Locations** smart button + count on company clients.
- The visit's area (stored, related to its contact) with an
  **Area / District group-by** on the dispatch board — technician routes
  by area in one click.
- The Contract Cockpit shows the service address's area.

## Working rule

Set the area on the **location contact**, not in free text on the
contract — everything downstream (visits, routing, cockpit) follows the
contact automatically, including when the area is later corrected.
