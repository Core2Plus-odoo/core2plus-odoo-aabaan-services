# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields, models


class AabaanServiceTag(models.Model):
    _name = 'aabaan.service.tag'
    _description = "Service Tag (per-site service labels on a contract)"
    _order = 'name'

    name = fields.Char(required=True)
    color = fields.Integer(default=0)

    # Odoo 19 constraint definition — the _sql_constraints list is
    # deprecated and warns on every registry load.
    _name_uniq = models.Constraint(
        'unique(name)',
        "A service tag with this name already exists.")
