# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    """Health and DM card expiry, next to the standard visa expiry, for the
    Budget Dashboard's Renewals & Compliance section. Dubai Municipality and
    health cards have no standard field in Odoo."""
    _inherit = 'hr.employee'

    fm_health_card_expiry = fields.Date(string='Health Card Expiry', groups='hr.group_hr_user')
    fm_dm_card_expiry = fields.Date(string='DM Card Expiry', groups='hr.group_hr_user')
