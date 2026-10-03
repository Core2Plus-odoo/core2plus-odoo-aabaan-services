# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    aabaan_order_id = fields.Many2one(
        'sale.order', string="Service Contract",
        compute='_compute_aabaan_contract')
    aabaan_end_date = fields.Date(
        string="Contract End", compute='_compute_aabaan_contract')
    aabaan_renewal_state = fields.Selection([
        ('overdue', 'Past end of term'),
        ('window', 'Renewal window (90 days)'),
        ('running', 'Running'),
        ('none', 'No end date'),
    ], string="Renewal", compute='_compute_aabaan_contract')
    aabaan_visits_done = fields.Integer(
        string="Visits Completed", compute='_compute_aabaan_contract')
    aabaan_visits_total = fields.Integer(
        string="Visits Planned", compute='_compute_aabaan_contract')
    aabaan_visits_overdue = fields.Integer(
        string="Visits Overdue", compute='_compute_aabaan_contract')
    aabaan_health = fields.Float(
        string="Contract Health (0-10)", compute='_compute_aabaan_contract',
        digits=(3, 1))
    aabaan_health_note = fields.Char(
        string="Health Basis", compute='_compute_aabaan_contract')
    aabaan_outstanding = fields.Monetary(
        string="Contract Outstanding", compute='_compute_aabaan_contract',
        currency_field='currency_id',
        help="Residual across all posted invoices of the contract, "
             "not just this one.")

    def _compute_aabaan_contract(self):
        line_has_sale = 'sale_line_ids' in self.env['account.move.line']._fields
        for move in self:
            order = self.env['sale.order']
            if line_has_sale and move.move_type in ('out_invoice', 'out_refund'):
                order = move.line_ids.sale_line_ids.order_id[:1]
            move.aabaan_order_id = order
            move.aabaan_end_date = (
                order['end_date']
                if order and 'end_date' in order._fields else False)
            move.aabaan_renewal_state = order.cockpit_renewal_state if order else False
            move.aabaan_visits_done = order.cockpit_visits_done if order else 0
            move.aabaan_visits_total = order.cockpit_visits_total if order else 0
            move.aabaan_visits_overdue = order.cockpit_visits_overdue if order else 0
            move.aabaan_health = order.cockpit_health if order else 0.0
            move.aabaan_health_note = order.cockpit_health_note if order else False
            move.aabaan_outstanding = order.cockpit_outstanding if order else 0.0

    def action_open_contract(self):
        self.ensure_one()
        if not self.aabaan_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.aabaan_order_id.name,
            'res_model': 'sale.order',
            'res_id': self.aabaan_order_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
