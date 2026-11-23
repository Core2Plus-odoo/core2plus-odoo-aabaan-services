# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Re-derive the branch of invoices that had none, now that the
    customer's contract and other invoices are consulted too."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env['account.move'].search([
        ('move_type', 'in', ('out_invoice', 'out_refund')),
        ('fm_cc_branch_id', '=', False)])
    env.add_to_compute(env['account.move']._fields['fm_cc_branch_id'], moves)
    moves._recompute_recordset(['fm_cc_branch_id'])
