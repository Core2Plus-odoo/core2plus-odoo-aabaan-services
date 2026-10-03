# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields, models


class SaleOrder(models.Model):
    """Let a contract name the branch that runs it.

    The Emirate analytic accounts are the branches, so this is an explicit
    link to one of them rather than a new dimension. ``aabaan_finance_core``
    prefers this link when it fills the analytic distribution on the
    invoice, instead of matching the ``x_emirate_regime`` label against
    account names — which is the fuzzy step that leaves a posting blocked
    when no name matches.
    """

    _inherit = 'sale.order'

    aabaan_branch_id = fields.Many2one(
        'account.analytic.account',
        string="Branch",
        domain="[('root_plan_id.name', 'ilike', 'emirate')]",
        tracking=True,
        help="The emirate branch delivering this contract. Sets the Emirate "
             "analytic tag on the invoices raised from it. Leave empty to "
             "fall back to the contract's Emirate field.")
