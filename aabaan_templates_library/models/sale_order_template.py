# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields, models


class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    aabaan_line_count = fields.Integer(
        string="Template Lines", compute='_compute_aabaan_counts')
    aabaan_usage_count = fields.Integer(
        string="Quotations Using It", compute='_compute_aabaan_counts')

    def _compute_aabaan_counts(self):
        Sale = self.env['sale.order']
        usage = {}
        if 'sale_order_template_id' in Sale._fields and self.ids:
            usage = {
                tmpl.id: count
                for tmpl, count in Sale._read_group(
                    [('sale_order_template_id', 'in', self.ids)],
                    ['sale_order_template_id'], ['__count'])
            }
        for template in self:
            template.aabaan_line_count = len(
                template.sale_order_template_line_ids)
            template.aabaan_usage_count = usage.get(template.id, 0)

    def action_view_usage(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'sale.order',
            'domain': [('sale_order_template_id', '=', self.id)],
            'views': [(False, 'list'), (False, 'form')],
            'target': 'current',
        }
