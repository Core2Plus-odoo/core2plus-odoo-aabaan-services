# -*- coding: utf-8 -*-
from odoo import api, fields, models

LOCATIONS = [
    ('ajman', 'Ajman'),
    ('sharjah', 'Sharjah'),
    ('dubai', 'Dubai'),
    ('fujairah', 'Fujairah'),
    ('pakistan', 'Pakistan office'),
]
COST_GROUPS = [
    ('payroll', 'Payroll'),
    ('vehicles', 'Vehicles & fuel'),
    ('licences', 'Licences, visas & fees'),
    ('chemicals', 'Chemicals & supplies'),
    ('rent', 'Office rent'),
    ('running', 'Office running'),
    ('other', 'Other costs'),
]


class FmCcBudget(models.Model):
    """Planned spend per month, location and cost group, read by the
    Expenses & Margin section (budget vs actual).

    Not Odoo's Budget app: that measures actuals through analytic
    accounts, and Aaban's expenses carry no analytic distribution, so its
    actual column would read zero. These are the figures of the client's
    own budget sheet; when expenses are tagged by branch the native app
    can take over."""
    _name = 'fm.cc.budget'
    _description = 'CEO Dashboard — budget line'
    _order = 'month, location, cost_group'

    month = fields.Date(required=True, help='Any day of the month; stored as the 1st.')
    location = fields.Selection(LOCATIONS, required=True)
    cost_group = fields.Selection(COST_GROUPS, required=True, default='other')
    amount = fields.Float(string='Budget (AED)', required=True, digits=(16, 2))
    note = fields.Char()

    _line_unique = models.Constraint(
        'UNIQUE(month, location, cost_group)',
        'One budget figure per month, location and cost group.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('month'):
                vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('month'):
            vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().write(vals)
