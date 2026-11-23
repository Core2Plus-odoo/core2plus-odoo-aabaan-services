# FM Command Centre — CEO Dashboard

One monthly page laid out after the client's PDF *"Aaban CEO Dashboard — AMC vs
Cash"* ("Two Businesses, One View"). Every figure is read live from Odoo.

Two menus, one page:

* **CEO Dashboard** — the 11-page PDF (`Aaban_CEO_Dashboard_A1MC_vs_Cash.pdf`), 10 sections.
* **CEO Summary** — the 9-page PDF (`Aaban_CEO_Dashboard_AMC_vs_Cash.pdf`): the
  same without Revenue by Service / Services by Emirate, sections renumbered
  1–8 (client action param `variant: compact`).

Menu: **Command Centre → CEO Dashboard** (group *Command Centre Viewer*;
Settings admins have it by default). Toolbar: month picker, *Include draft
invoices* toggle, refresh, **Print / PDF** (one section per A4 page).

## Sections and sources

| # | Section | Source |
|---|---|---|
| cover | Total revenue, target, jobs, new clients, receivables, margin | sections below |
| 1 | AMC vs Cash, 12-month trend | customer invoices (excl. VAT) by `invoice_date`, split by `account.move.fm_cc_stream` |
| 2 | AMC Department | confirmed FM contracts (`sale.order`, `is_fm_contract`): active / new / renewal (customer had an earlier contract) / ending in 60 days; FSM visits done vs planned |
| 3 | Cash Sales | cash-stream invoices; payments (`account.payment`) by journal → Cash / Card / Bank; cash-journal statements for the daily cash match |
| 4 | Branch Scorecard | revenue by `fm_cc_branch_id` vs `fm.branch` AMC + cash targets |
| 5–6 | Services | invoice lines by `account.move.line.fm_cc_service` × stream × branch |
| 7 | Credit Recovery | open invoices (`amount_residual > 0`) aged from the invoice date: 0–30 / 31–60 / 61–90 (cash only) / 90+ (CEO) |
| 8 | Sales Team | AMC deals = contracts starting in the month by `user_id`; cash deals = cash invoices by `invoice_user_id`; targets in `fm.cc.sales.target` |
| 9 | Expenses & Margin | posted expense-account lines by account; margin vs company target |
| 10 | Cash & Bank | bank/cash journal accounts, posted only; YTD flows vs last year |

## Classification (stored, editable)

* `product.template.fm_cc_stream` / `fm_cc_service` — guessed from the product
  name ("Cash" → cash, "Contract"/"AMC" → AMC; service by keyword). Products
  sold on confirmed contracts are marked AMC on install.
* `account.move.fm_cc_stream` — sale order → product stream → customer holds a
  confirmed contract (AMC) → otherwise cash.
* `account.move.fm_cc_branch_id` — `branch_id` → sale order → emirate in the
  product name → customer city → customer's contract → emirate named most on
  the customer's other invoices. What is left shows as *Unassigned*.
* `sale.order.fm_cc_branch_id`, `project.task.fm_cc_branch_id` likewise.

Corrections: **Command Centre → Configuration** (Branch Targets, Sales Team
Targets, Service Classification, Invoice Classification, Dashboard Settings).
