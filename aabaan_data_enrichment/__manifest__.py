# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Data Enrichment',
    'version': '19.0.1.1.0',
    'post_init_hook': '_post_init_hook',
    'category': 'Sales/Sales',
    'summary': 'Auto-tag contract emirates and enrich customer contacts from real evidence',
    'description': """
Two idempotent sweeps, run on install and re-runnable from the Action
menu. Both fill ONLY empty fields and post their evidence in the chatter
— human-entered data is never overwritten, and nothing is invented:

- Tag Contract Emirates: every contract without x_emirate_regime is
  tagged from the service address, the customer address, the customer
  name or the contract text (whole-word emirate matching, selection keys
  resolved at runtime).
- Enrich Contacts: customers get their UAE state + country from their own
  address/name or from the emirate tagged on their contracts, and an
  industry from confident name keywords (cafeteria, hypermarket, school,
  hospital, contracting, hotel, ...) mapped onto the NATIVE industry
  list — powering the CEO dashboard's industry breakdown.

Contracts or contacts without usable evidence are left untouched and
counted in the summary notification.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['aabaan_visit_schedule'],
    'data': [
        'data/server_actions.xml',
    ],
    'installable': True,
    'application': False,
}
