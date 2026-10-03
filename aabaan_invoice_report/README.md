# Aabaan Invoice Report

The Tax Invoice screen from the approved UI reference. Standard-first: this
doesn't touch the native invoice print action — it adds a new one
("Tax Invoice (Aaban)") to the Print menu on customer invoices and credit
notes, on the same Aaban letterhead as the quotation PDF.

## What is code (this module)

- **Tax Invoice PDF** — every field FTA requires (Federal Decree-Law No. 8
  of 2017 / Cabinet Decision 52): the words "Tax Invoice" (or "Tax Credit
  Note") shown clearly, supplier name/address/TRN/trade licence, recipient
  name/address and TRN when registered, a sequential invoice number, the
  invoice date, date of supply when it differs from the invoice date
  (native `delivery_date`, only shown if set), payment due date,
  description/qty/unit price/discount/VAT rate per line, the VAT breakdown,
  and the grand total in words. A reverse-charge notice appears only when
  the invoice's own fiscal position is actually configured for it — never
  asserted by default. A Payment Details line appears only if the issuing
  company has a real bank account on file.
- **Document Audit Trail** — a new tab on the invoice form, built entirely
  from data the system already has: created (who/when), posted (journal
  entry date, once posted), sent to customer (a real `mail.mail` record in
  `state='sent'`, not assumed), payments received (real
  `account.partial.reconcile` records against the invoice's receivable
  line, with the actual reconciled amount and the payment's journal), and
  credit notes issued against it. A milestone that hasn't happened yet
  simply doesn't appear in the trail — nothing here is estimated or
  reconstructed.

## What is deliberately guarded, not assumed

- The reverse-charge statement only prints if a real fiscal position on
  the invoice is configured for it.
- Payment Details only prints if the company has a real bank account.
- Date of Supply only prints if it's set and differs from the invoice
  date — this database has no separate tax-point workflow, so most
  invoices show only the invoice date, which is correct.

## What is configuration (native Odoo)

- Company bank accounts, for the Payment Details block to appear.
- Fiscal positions, if a reverse-charge scenario is ever configured.
