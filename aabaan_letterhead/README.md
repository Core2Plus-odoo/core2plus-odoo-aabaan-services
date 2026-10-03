# Aabaan Letterhead

Cleanup-audit consolidation: the letterhead header/footer existed in
**three copies** (quotation report, service documents, tax invoice) and two
print helpers in two. This module now owns the single canonical version.

## What is code (this module)

- `aabaan_letterhead.header` / `aabaan_letterhead.footer` — the flat
  two-tone-band letterhead. Callers set `company` in scope and `t-call`.
  CSS triangles are banned from this letterhead: they render unreliably in
  wkhtmltopdf, which is why the quotation abandoned them first.
- `tools.line_desc(line)` — line description without the internal product
  code prefix.
- `tools.amount_in_words(record)` — grand total in words, `''` when the
  currency cannot spell it.

The report modules keep thin, identically-named wrapper methods
(`_aabaan_line_desc`, `_aabaan_amount_in_words`) because QWeb calls them
on the record — the logic lives once, here.

## Intentional visual change on consolidation

Quotations and tax invoices print **byte-identically** to before (their
markup was the canonical source). Service documents (visit report, tank
certificate, termite warranty) previously still used the old
CSS-triangle band and a short footer — they now get the flat band and the
full offices footer. That is an intended alignment, not an accident.

## Editing the letterhead

Edit it **here and only here**. If a document needs something the shared
letterhead doesn't carry, that content belongs in the document's own
body, not in a fork of the letterhead.
