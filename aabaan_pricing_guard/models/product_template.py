# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    aabaan_line_usage = fields.Integer(
        string="Used on Order Lines", compute='_compute_aabaan_line_usage',
        help="How many sale order lines have ever referenced this product. "
             "A zero-priced product with no usage is safe to archive; one "
             "that is in use needs its price fixed instead.")
    aabaan_confirmed_usage = fields.Integer(
        string="Of Which Confirmed", compute='_compute_aabaan_line_usage',
        help="Usage on confirmed orders — these already billed at the "
             "recorded price, so archiving the product will not change them.")

    @api.depends('product_variant_ids')
    def _compute_aabaan_line_usage(self):
        """Batched: two grouped queries for the whole recordset rather than
        a count per row, so this stays usable as a list column."""
        Line = self.env['sale.order.line']
        variants = self.mapped('product_variant_ids')
        totals, confirmed = {}, {}
        if variants:
            for product, count in Line._read_group(
                    [('product_id', 'in', variants.ids)],
                    ['product_id'], ['__count']):
                totals[product.id] = count
            for product, count in Line._read_group(
                    [('product_id', 'in', variants.ids),
                     ('state', '=', 'sale')],
                    ['product_id'], ['__count']):
                confirmed[product.id] = count
        for template in self:
            ids = template.product_variant_ids.ids
            template.aabaan_line_usage = sum(totals.get(i, 0) for i in ids)
            template.aabaan_confirmed_usage = sum(
                confirmed.get(i, 0) for i in ids)
