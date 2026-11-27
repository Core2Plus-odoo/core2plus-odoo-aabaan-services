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

PAYMENT_PLANS = [
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly / 2-monthly'),
    ('mixed', 'Monthly + 6-monthly'),
    ('yearly', 'Yearly'),
]
DETAIL_BASIS = [('month', 'per month'), ('year', 'per year')]


class FmCcBudgetCategory(models.Model):
    """A line of the budget sheet (Fuel, Visa Renewal, ...): the cost group
    it rolls up to, how it is paid, and what the sheet's detail tab says it
    should cost, which the Budget Checks section compares with the plan."""
    _name = 'fm.cc.budget.category'
    _description = 'CEO Dashboard — budget category'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    cost_group = fields.Selection(COST_GROUPS, required=True, default='other')
    payment_plan = fields.Selection(PAYMENT_PLANS, required=True, default='monthly')
    unit_cost = fields.Float(
        string='Cost per item (AED)',
        help='For renewals counted per person or vehicle, e.g. one visa renewal.')
    detail_amount = fields.Float(
        string='Detail tab amount (AED)',
        help="What the budget sheet's detail tab works out for this category; "
             'the Budget Checks section compares it with the monthly plan.')
    detail_basis = fields.Selection(DETAIL_BASIS, default='month')
    detail_note = fields.Char(help='How the detail tab states it, e.g. "AED 2,000 per branch".')

    _name_unique = models.Constraint('UNIQUE(name)', 'Category names must be unique.')


class FmCcBudget(models.Model):
    """Planned spend per month, location and category, read by the Budget
    Dashboard and the Expenses & Margin section (budget vs actual).

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
    category_id = fields.Many2one('fm.cc.budget.category', index=True, ondelete='restrict')
    cost_group = fields.Selection(
        COST_GROUPS, required=True,
        compute='_compute_cost_group', store=True, readonly=False, precompute=True)
    amount = fields.Float(string='Budget (AED)', required=True, digits=(16, 2))
    note = fields.Char()

    _line_unique = models.Constraint(
        'UNIQUE(month, location, cost_group, category_id)',
        'One budget figure per month, location and category.')

    @api.depends('category_id')
    def _compute_cost_group(self):
        for line in self:
            if line.category_id:
                line.cost_group = line.category_id.cost_group
            elif not line.cost_group:
                line.cost_group = 'other'

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
