# Aabaan Menu & UX

One module that owns the menu information architecture, instead of every
module adding a top-level entry where it happened to be built. Nothing is
deleted and no action changes — existing menus are **re-parented**:

```
Sales
├── Contracts                 ← section
│   ├── Contract Register     (the Contract Cockpit list)
│   └── Templates Library
└── Aabaan Setup              ← section
    ├── Service Tags
    └── Zero-Priced Products
```

The Command Centre keeps its own top-level app entry — it is an
application, not a Sales sub-screen.

## What is code (this module)

Only `ir.ui.menu` re-parenting records and the two section menus. No
models, no logic.

## Partial-upgrade note (the one gotcha)

A menu-owning module re-asserts its original parent when **it alone** is
updated (`-u aabaan_templates_library` would move Templates Library back
to the top level). Updating `aabaan_ux` afterwards restores the
structure — include it in any module-update list that touches
`aabaan_contract_cockpit`, `aabaan_templates_library`,
`aabaan_service_contracts` or `aabaan_pricing_guard`.

## What is configuration (native Odoo)

Nothing — users' favourite menus and the Ctrl+K palette pick up the new
structure automatically.
