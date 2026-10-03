# Aabaan Odoo build — working rules

Custom Odoo 19 Enterprise addons for Aaban Classic Building Cleaning L.L.C.
(`core2plus-odoo-aabaan.odoo.com`, Odoo.sh, deploys from `main`).

## Rule 1 — Standard-first, always

**If native Odoo does it, configure it — never rebuild it.** This is a standing
client instruction and applies to every feature, every priority, every module:

1. First: native Odoo app/feature + configuration (document the config steps).
2. Second: a thin extension of a native model/view (fields, guards, reports).
3. Last resort: custom logic — only for what native Odoo genuinely cannot do,
   and say so explicitly in the PR.

Never create new top-level models when a native model can carry the data.
Installing a native module (e.g. `purchase`, `hr`, `fleet`) counts as
standard-first when a written business justification exists — the handoff's
"install nothing without justification" rule still applies.

## Rule 2 — The database defines the x_* fields

The `x_*` fields on `sale.order` / `project.task` are **manual fields living in
the production database**, not in this repo. Modules must resolve them at
runtime (guard with `in self._fields`, match selection keys by substring) and
degrade to empty states when absent — never redefine them in Python.

## Rule 3 — Production guard

The legacy database `aaban-classic-building-cleaning-llc` is read-only,
forever. Every script that touches an Odoo instance asserts it is not
targeting it. API keys live in env vars, never in committed files.

## Rule 4 — No invented numbers

Figures shown to the business come from the database, the master data sheet,
or the signed documents — labelled with their source. Where a fact is unknown,
say so; an invented number costs more than a question.

## Conventions

- One working branch (`claude/new-session-*`); restart it from `origin/main`
  after each merge; every change lands as a PR the client merges.
- Brand: letterhead ink `#17171a`, orange `#ef7d25`; client name leads visit
  titles; contacts are 800 AABAN (800 22226), 055 859 8834, 055 866 6530,
  infoaabanservices@gmail.com — no landline.
- Fool-proof means: the easy path is the correct path and the wrong path is
  blocked with a reason (see `aabaan_field_ops`, `aabaan_finance_core`).
- Modules are tested (`post_install`), version-bumped on change, and each
  README documents what is code vs. what is configuration.
- The environment usually cannot reach `*.odoo.com` — say so instead of
  guessing live state; verification steps go in the PR body.
