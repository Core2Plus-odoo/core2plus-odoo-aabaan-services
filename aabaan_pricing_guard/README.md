# Aabaan Pricing Guard

Closes the underbilling hole flagged in the business model review (§4.4):
the catalogue carries legacy duplicate SKUs priced at **AED 0** —
`AAB-PEST`, `AAB-WATER`, `AAB-ANTI`, `AAB-DEEP`, `AAB-SOFA`,
`AAB-ATTESTAION` and three `AAB-LAB` lines — sitting alongside the
correctly priced products. Picking the wrong one on a quotation silently
bills nothing, and nothing in the system stops it.

## What is code (this module)

**The confirmation gate.** A quotation cannot be confirmed while any
product line would bill nothing. The error names the offending lines and
states both ways out rather than just refusing:

> `S00123 cannot be confirmed — these lines would bill nothing:`
> `  • AAB-PEST`
> `Either set the correct price (the catalogue holds legacy duplicate
> products priced at AED 0 — check you picked the priced one), or tick
> "Intentionally Free" on the line and give the reason, if the work really
> is not being charged.`

It measures the **line subtotal**, not the unit price — so a 100% discount
is caught as well as an AED 0 product. Both underbill identically, and only
checking the unit price would let the discount route straight through.

**Deliberately free work stays easy.** Free follow-ups (the 3-day rule),
call-outs covered by the Dubai LO 11 / Article 5 entitlement, and agreed
goodwill are one tick away — but the tick requires a written reason, so it
is an audit trail rather than a silent bypass. A line that bills nothing
has to be explainable months later.

**Zero-Priced Products review** (Sales → Zero-Priced Products). Every
sellable AED 0 product with how many order lines reference it and how many
of those are on confirmed orders:

- **Greyed out** — never used. Safe to archive.
- **Red** — already on confirmed orders. Fix the price; do not archive, or
  those orders lose their product reference.

That turns "recommend confirming unused, then archiving" from a guess into
a decision made on evidence.

## What is configuration (native Odoo)

- **Archiving the duplicate SKUs** is done from the review screen above,
  once the usage counts confirm which are unused. This module deliberately
  does not archive anything automatically — that is a catalogue decision,
  and an automatic sweep could archive a product someone is mid-quotation
  on.
- Correcting the price on a duplicate that *is* in use is ordinary product
  maintenance.

The guard holds whether or not the duplicates are ever archived, so the
revenue leak is closed today and the catalogue cleanup can happen when the
client has time to confirm it.

## Interaction with existing free-visit flows

The free follow-up raised by `aabaan_field_ops` on an infestation creates a
**`project.task`**, not a zero-priced order line, so this guard does not
interfere with it. Nothing in the repo auto-creates sale order lines —
verified before building — so the gate only ever fires on lines a human
put there.
