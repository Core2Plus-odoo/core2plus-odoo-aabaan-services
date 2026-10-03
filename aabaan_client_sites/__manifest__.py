# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Client Sites & Areas',
    'version': '19.0.1.5.0',
    'category': 'Sales/CRM',
    'post_init_hook': '_post_init_hook',
    'summary': 'Areas on contacts and multi-location clients, wired through visits and contracts',
    'description': """
A single client can have many service locations. The native structure
carries it — each location is a child contact (Delivery Address) of the
client, picked as the service address on the contract — and this module
adds the missing UAE concept on top:

- Area / District on every contact (Al Nuaimiya, Abu Hail, ...), shown in
  the address block and the contacts list.
- A Locations smart button on company clients, opening (and pre-filling)
  their site contacts.
- The visit inherits the area from its contact (stored) — the dispatch
  board and visit lists get an "Area / District" group-by for building
  technician routes.
- The Contract Cockpit shows the service address's area.

No new models — locations are native child contacts; the area is one
indexed field carried through by related fields.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['aabaan_field_ops', 'aabaan_contract_cockpit'],
    'data': [
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
}
