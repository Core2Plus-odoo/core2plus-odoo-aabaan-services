# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Menu & UX',
    'version': '19.0.1.0.1',
    'category': 'Hidden/Tools',
    'summary': 'One deliberate information architecture for the Aabaan menus',
    'description': """
The Aabaan modules each added their menu item where it was built, one PR at
a time, which left the Sales app top bar with four unrelated entries. This
module owns the information architecture in one place and REORGANISES the
existing menus rather than duplicating them (nothing is deleted, no action
changes). The structure::

    Sales
    - Contracts (section)
        - Contract Register (the Contract Cockpit list)
        - Templates Library
    - Aabaan Setup (section)
        - Service Tags
        - Zero-Priced Products

Note for partial upgrades: a menu-owning module re-asserts its original
parent when IT alone is updated. Updating this module afterwards restores
the structure — include aabaan_ux in any module-update list that touches
the menu owners.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'aabaan_contract_cockpit',
        'aabaan_templates_library',
        'aabaan_service_contracts',
        'aabaan_pricing_guard',
    ],
    'data': [
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
