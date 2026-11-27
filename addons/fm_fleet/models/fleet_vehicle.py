# -*- coding: utf-8 -*-
from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    fm_branch_id = fields.Many2one('fm.branch', string='FM Branch', index=True, tracking=True)
    fm_registration_expiry = fields.Date(string='Registration Expiry', tracking=True)
    fm_insurance_expiry = fields.Date(string='Insurance Expiry', tracking=True)
