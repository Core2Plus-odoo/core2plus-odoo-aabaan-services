# Aabaan Service Documents

The documents every visit promises — printed from the visit's Print menu,
in the letterhead style shared with the quotation report.

## What is code (this module)

| Document | Guard |
|---|---|
| Service Report | prints any time; DRAFT banner until the visit is completed |
| Water-Tank Cleaning & Disinfection Certificate | completed **tank** jobs only |
| Anti-Termite Warranty Certificate (10-year, computed end date) | completed **termite** jobs only |

Fool-proof: printing the wrong certificate is blocked with a reason. The
service kind is detected from the contract's service line, its order lines
and the visit name; if none of those mention the service, the fix is to
set the service line on the contract.

All values resolve at runtime (`x_visit_type`, `x_emirate_regime`,
`x_service_line` may be absent) — the documents degrade to fewer rows,
never to errors. Times print in the user's timezone.

## What is configuration (native Odoo)

- Company logo, TRN (`vat`) and Trade Licence (`company_registry`) on the
  company record feed the letterhead and footer.
- The technician shown is the visit's assignee; check-in/out and findings
  come from the Field Ops buttons (Start / Complete Visit).
