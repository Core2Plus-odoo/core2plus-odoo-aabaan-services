# Aabaan Quotation Report (`aabaan_quotation_report`)

Replaces the standard sale quotation/order PDF with the **Aaban Services
letterhead layout**, matching the company's own signed contract documents
(black angular header band with orange slash, logo + tagline top right,
Ref#/Date block, Subject line, First/Second Party intro, contract Articles,
orange line-items table, amount in words, signature blocks, offices footer).

## What changes

`sale.action_report_saleorder` (the report behind **Print → Quotation /
Order**, the emailed PDF and the customer portal download) is redirected to
`aabaan_quotation_report.report_saleorder_aabaan`, printed on a dedicated
A4 letterhead paper format with room for the branded header and footer.

Compared to the historical Word letterhead, the layout adds what a compliant
tax document needs: a VAT breakdown (subtotal / VAT / grand total), the
TRN and trade licence number in the footer, LPO reference, validity date,
and the customer's digital signature when the order was signed via the
portal.

## Content sources — nothing is hard-coded except the letterhead offices

- Logo: `res.company.logo` (falls back to the company name in brand orange).
- TRN / trade licence: `res.company.vat` / `company_registry`.
- Contract Articles: the order's terms (`note`), which the six quotation
  templates carry from Aabaan's signed agreements.
- Subject: built from the order's `x_service_line` and `x_site_address`
  (resolved at runtime; missing fields degrade to an empty subject).
- Title: "Quotation" while draft/sent, "Contract" once confirmed.
- **Static, from the client's letterhead:** the Head Office / Branch Offices
  block, phone numbers and email address. ⚠ The head office printed is
  Deira, Dubai — this ties into open question #2 of the build handoff (the
  Dubai entity/licence). If that question resolves differently, update the
  footer block in `report/quotation_report.xml`.

## Revert

Point `sale.action_report_saleorder`'s `report_name` and `report_file` back
to `sale.report_saleorder` (Settings → Technical → Reports), or uninstall
this module and restore those two fields.
