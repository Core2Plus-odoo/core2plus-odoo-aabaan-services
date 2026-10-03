from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_finance_core import _seed_finance_config


def migrate(cr, version):
    """§7/§11 seeding (expense accounts, cash + petty-cash journals per
    company) and the §5 recovery grid's service dimension backfilled on
    existing customer invoices."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_finance_config(env)
    Move = env['account.move']
    if 'aabaan_services' in Move._fields:
        moves = Move.search(
            [('move_type', 'in', ('out_invoice', 'out_refund'))])
        env.add_to_compute(Move._fields['aabaan_services'], moves)
        Move.flush_model(['aabaan_services'])
