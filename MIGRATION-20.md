# Odoo 19 → 20 migration and standard-first audit

Everything below was checked against the real Odoo 20 source, not from
memory: `odoo/odoo` branch `20.0` at commit `b100a87`. Where a claim could
not be verified first-hand it is listed under *Not verified* rather than
asserted.

## 1. Breaking changes found and fixed

| # | Change in Odoo 20 | Evidence | What we did |
| - | - | - | - |
| 1 | `ir.model.access` replaced by `ir.access`; access rights and record rules unified into one model with an `operation` letter column and a `domain` column | `odoo/addons/base/models/ir_access.py:66`; `ir.rule` no longer defined in base; 226 native `ir.access.csv` files vs 0 `ir.model.access.csv` | Converted our one security file to `security/ir.access.csv` with the native header `id,name,model_id,group_id/id,operation,domain`; manifest updated |
| 2 | `Model.check_access_rights()` and `name_get()` removed; access checks are `check_access(operation)` | `odoo/orm/models.py:3443`; no `def name_get` in the ORM | `tools/fta_archive.py` read-only RPC allowlist corrected |
| 3 | `_sql_constraints` no longer supported (warns at registry load) | `odoo/orm/model_classes.py:175` | No code change needed — `aabaan_service_contracts` already uses `models.Constraint`; stale comment corrected |

`operation` is a subset of `crud` (`c`=create, `r`=read, `u`=write,
`d`=unlink), per `CRUD_SELECTION` in `ir_access.py`. The bare `model_id`
column resolves by model name because `ir.model._rec_names_search =
('name', 'model')`.

Our four access rows mapped as: `1,1,1,1` → `crud`, and the
contract-document user row `1,1,1,0` → `cru`.

## 2. Version bump

All 18 manifests moved `19.0.x` → `20.0.x`, each module keeping its own
sub-version so the change history encoded there survives.

The `migrations/` folders stay named `19.0.*` deliberately: Odoo runs a
migration script when its version is greater than the installed version,
and `19.0.x < 20.0.x`, so renaming them would break the upgrade path from
the current production state.

## 3. Dependencies: intact

Every `depends` across the 18 modules still exists in Odoo 20. Three are
Enterprise-only and therefore absent from the community repo, which is
expected for this build, not a removal: `industry_fsm_sale`,
`sale_subscription`, `hr_payroll`. All 11 native models we extend still
exist in 20, including `sale.order.template` (`sale_management`). The only
two group xmlids we reference, `sales_team.group_sale_salesman` and
`sales_team.group_sale_manager`, both still exist.

## 4. Standard-first audit (Rule 1)

Checked each custom model against what Odoo 20 natively provides.

**Compliant — leave alone**

- `aabaan.ceo.dashboard` is an `AbstractModel`. It stores no data; it is a
  data provider for the OWL client action. No top-level data model.
- `aabaan_branches` carries the emirates as `account.analytic.account`
  records — analytic distribution is Odoo's own dimension mechanism — and
  adds only a trade-licence field. Native `res.company` branches
  (`parent_id`/`child_ids`, `res_company.py:87`) exist, but they create
  separate accounting entities with their own sequences; the analytic
  dimension is the lighter and more standard fit for one company trading
  across emirates. Flagging the alternative, recommending no change.
- `aabaan_visit_schedule` stays custom, now on evidence. Native
  `project.task.recurrence` is a rolling next-occurrence model
  (`repeat_interval`, `repeat_unit`, `repeat_type`, `repeat_until`) with no
  contract linkage, no forward-dated schedule the client can plan against,
  and no per-emirate legal cadence. It cannot express the AMC schedule.
- `aabaan_letterhead` is a deliberate de-duplication of one brand design
  that previously existed in three copies — a shared QWeb template, not a
  reimplementation of a native feature.

**Applied — clear wins**

- Expense selection now uses Odoo's own `internal_group` field instead of
  prefix-matching `account_type`. `internal_group` is literally
  `split_part(account_type, '_', 1)`
  (`account_account.py:707`) and is searchable, so this is behaviour-
  identical and no longer needs this repo to track the list of expense
  types. It was already drifting: Odoo 20 has **four** `expense*` types —
  `expense`, `expense_other`, `expense_depreciation`,
  `expense_direct_cost` — and the code comment named only three.
  Changed in `aabaan_ceo_dashboard` (domain) and `aabaan_finance_core`
  (record filter).

**Recommended, needs your decision — not applied**

- `aabaan.contract.document` is the one genuine Rule 1 finding. It is a new
  top-level model that stores a file plus `document_type` and
  `valid_until`. Its `datas` field already uses `attachment=True`, so the
  bytes live in `ir.attachment` regardless — the custom model is a wrapper
  around a native attachment. The standard-first form is a thin extension
  of `ir.attachment` with those two fields, exposed as a filtered
  One2many on the contract. Not applied here because existing production
  records would need a data migration, which is your call, not a
  refactor I should make silently.
- `aabaan.service.tag` could be `product.tag` (`addons/product/models/
  product_tag.py:8`), since what is delivered at a site is a product.
  Per-app tag models are idiomatic Odoo (`crm.tag`, `project.tags`), so
  this is defensible as-is; mentioned for completeness. Also a data
  migration.
- `aabaan.contract.site` has no native equivalent — it is a
  `sale.order` ↔ `res.partner` relation carrying its own agreed terms.
  Custom is justified.

## 5. Native modules to install

No native Odoo 20 module cleanly replaces an existing custom module, so
there is nothing here to install in place of code. Specifically:
`sale_pdf_quote_builder` is new and native, but it is `auto_install: True`
alongside `sale_management`, so it is already present, and it works by
merging PDF documents onto a quotation rather than by QWeb layout — a
different mechanism from `aabaan_quotation_report`, not a drop-in
replacement. The standard-first gains above are reuse of native *fields and
models* (`internal_group`, `ir.attachment`, `product.tag`), not new installs.

## 6. Not verified — remaining risk

This is the honest limit of what was done here.

- **Nothing was run.** No Odoo 20 instance or database was reachable from
  this environment, so no module was installed, upgraded or tested. The
  checks that did pass are static: all 127 Python files compile, all 42 XML
  files are well-formed, all 18 manifests parse, and the new access CSV has
  a valid header and operations.
- **Enterprise code was not inspected.** `industry_fsm_sale`,
  `sale_subscription` and `hr_payroll` are not in the community repo, so
  the API surface that `aabaan_visit_schedule`, `aabaan_ceo_dashboard` and
  `aabaan_hr_fleet` build on is unverified for 20.
- **Front-end assets were not checked.** `aabaan_ceo_dashboard` (178 lines
  of OWL JS, 378 SCSS) and `aabaan_website_theme` (759 XML, 442 SCSS) are
  the most likely remaining breakage: OWL APIs and website snippet
  templates move between major versions. These need a real upgrade run.
- The `x_*` fields remain manual database fields per Rule 2 and were not
  touched; their presence on Odoo 20 needs checking in the database.

Suggested next step: an Odoo.sh staging branch on 20.0, upgrade the
database there, then work the install/upgrade log and the `post_install`
test suites.
