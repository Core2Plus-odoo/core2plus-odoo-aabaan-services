# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    """The Emirate analytic accounts are the operating branches.

    The plan itself lives in the production database (Rule 2). This layer
    only adds the trade licence each branch trades under, so a branch's
    renewal is tracked where the branch is, rather than requiring a
    separate company per emirate.
    """

    _inherit = 'account.analytic.account'

    aabaan_licence_no = fields.Char(
        string="Trade Licence No.",
        help="From the branch's licence document. Only meaningful on the "
             "Emirate branch dimension.")
    aabaan_licence_expiry = fields.Date(
        string="Trade Licence Expiry",
        help="From the licence document. The daily check raises a renewal "
             "activity 60 days before expiry (and keeps it open while "
             "expired).")
