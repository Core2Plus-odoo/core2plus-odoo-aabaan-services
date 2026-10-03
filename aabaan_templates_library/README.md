# Aabaan Templates Library

The Templates Library screen from the approved UI set — a card gallery
for quotation templates.

## What is code (this module)

- Two computed counters on native `sale.order.template`: lines on the
  template and quotations created from it (batched `_read_group`).
- A kanban card gallery + `Sales > Templates Library` menu, with a
  "View quotations" drill per template.

## What is configuration (native Odoo)

- Creating and editing templates: native form (Sales > Configuration >
  Quotation Templates), untouched.
- Using a template on a quotation: native `Quotation Template` field.
