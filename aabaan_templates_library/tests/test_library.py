# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTemplatesLibrary(TransactionCase):

    def test_counts_compute(self):
        product = self.env['product.product'].create({
            'name': 'Library AMC (test)', 'type': 'service',
            'list_price': 100.0})
        template = self.env['sale.order.template'].create({
            'name': 'Library Test Template',
            'sale_order_template_line_ids': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 1})],
        })
        self.assertEqual(template.aabaan_line_count, 1)
        self.assertEqual(template.aabaan_usage_count, 0)
        partner = self.env['res.partner'].create({'name': 'Library Test Co'})
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'sale_order_template_id': template.id,
        })
        template.invalidate_recordset()
        self.assertEqual(template.aabaan_usage_count, 1)
        action = template.action_view_usage()
        self.assertEqual(action['res_model'], 'sale.order')
