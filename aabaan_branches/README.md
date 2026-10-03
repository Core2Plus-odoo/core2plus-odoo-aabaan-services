# Aabaan Branches

One company, several branches. Ajman (head office), Dubai and Sharjah are
run as **branches of the single Aaban company**, not as separate companies
in Odoo.

## What is code, what is configuration

**Configuration (lives in the production database):**

- The **Emirate analytic plan** and its accounts. This is the branch
  dimension. It is defined in the database, not in this repo (Rule 2), and
  is resolved at runtime by name. `aabaan_finance_core` already autofills
  it on invoice lines and enforces it on every posting.

**Code (this module):**

- `Trade Licence No.` and `Trade Licence Expiry` on each Emirate analytic
  account, so a branch's licence is tracked where the branch is.
- A daily check raising **one** open renewal activity 60 days before
  expiry — for the company licence and for every branch licence. An open
  activity blocks duplicates, so an expired licence does not re-alert
  daily.
- A **Branch** field on `sale.order`, searchable and groupable, pointing at
  an Emirate analytic account.
- Head-office contact data corrected from the letterhead where Odoo's demo
  placeholders were still in place.

## Why the branch drives the analytic tag

`aabaan_finance_core` fills the Emirate analytic tag on an invoice line by
reading the source contract's `x_emirate_regime` label and matching it
against analytic account names. That fuzzy step is what leaves a posting
blocked when no name matches.

When a contract names its Branch explicitly, finance core uses that link
instead and skips the matching. The lookup is runtime-guarded
(`'aabaan_branch_id' in order._fields`) because `aabaan_finance_core` does
not depend on this module, so it degrades to the old behaviour if this
module is absent.

## Licence facts

Transcribed from the licence documents; no figure is invented.

| Branch | Licence | Expires |
|---|---|---|
| Ajman (head office) | 103074 | 08-Jan-2027 |
| Dubai | 989256 | 13-Oct-2026 |
| Sharjah | 908692 | 01-Jul-2026 |

The letterhead's old registry **109374** appears on none of the licence
documents and is treated as a known-wrong placeholder, corrected wherever
it was used.

## Migrating from separate companies

Versions 19.0.2.x split Dubai and Sharjah into **standalone companies**.
Version 19.0.3.0.0 reverses that direction: the emirates are branches
again.

**Why.** The separate emirate licences exist because the UAE requires a
local licence to trade in each emirate — not because the business is three
businesses. Commercially and for tax it is one company: one taxable
person, one TRN, one set of statutory books. The Sharjah licence is
registered as *SHJ BR 2* — a branch registration — which is the same story
in the paperwork.

The upgrade **stops maintaining the split** and carries each company's
licence number and expiry onto the matching branch, so nothing is lost.
It does **not** merge the books, because:

> Odoo cannot move journal entries between companies.

Consolidating is an accounting exercise, not a migration. The
post-migration names any company still standing so the work is visible.

### Do it early

The cost of consolidating scales with posted entries. Moving a few dozen
is an afternoon; moving tens of thousands means re-posting balances by
hand and reconciling the result. Check the scope before deciding when:

```sql
SELECT c.name,
       (SELECT count(*) FROM account_move   m WHERE m.company_id = c.id) AS journal_entries,
       (SELECT count(*) FROM account_move_line l WHERE l.company_id = c.id) AS journal_items,
       (SELECT count(*) FROM sale_order     s WHERE s.company_id = c.id) AS orders,
       (SELECT count(*) FROM account_journal j WHERE j.company_id = c.id) AS journals
  FROM res_company c
 ORDER BY c.id;
```

### The procedure

Run by whoever owns the books, not by a migration:

1. **Stop posting** to the emirate companies — everything new goes to the
   surviving L.L.C.
2. **Close their periods** so nothing can be back-dated into them.
3. **Carry the balances across** with journal entries booked in the
   surviving company, one per emirate, referencing the source company in
   the narrative so the trail is auditable.
4. **Reconcile** — the surviving company's trial balance should absorb the
   others' closing balances exactly.
5. **Archive** the emptied companies. Never delete: the history has to
   stay readable.

Tag each carried-across entry with its Emirate analytic account on the way
in, and the branch P&L keeps its history rather than starting from the
consolidation date.

### Reporting after consolidation

Branch-wise P&L comes from the Emirate analytic dimension, which
`aabaan_finance_core` autofills from the contract and enforces on every
posting — so no untagged entry can leak out of a branch total. Use Odoo's
Profit & Loss report with an analytic filter.

Two limits worth knowing:

- Analytic splits the **P&L**, not the balance sheet. Receivables, payables
  and cash stay at company level.
- A *complete* branch P&L needs a rule for **shared overheads** (head
  office, group insurance, management salaries): either allocate them
  across branches or leave them at group level and accept that the branch
  P&Ls sum to less than the company. Either is defensible; it needs
  deciding rather than defaulting.
