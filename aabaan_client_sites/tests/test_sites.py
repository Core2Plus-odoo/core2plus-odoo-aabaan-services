# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestClientSites(TransactionCase):

    def test_locations_and_area_flow(self):
        client = self.env['res.partner'].create({
            'name': 'Sites Test Group', 'is_company': True})
        site = self.env['res.partner'].create({
            'name': 'Sites Test Group — Tower A',
            'parent_id': client.id, 'type': 'delivery',
            'aabaan_area': 'Al Nuaimiya'})
        client.invalidate_recordset()
        self.assertEqual(client.aabaan_location_count, 1)
        action = client.action_view_locations()
        self.assertEqual(action['res_model'], 'res.partner')

        project = self.env['project.project'].create({
            'name': 'Sites Test FSM', 'is_fsm': True})
        task = self.env['project.task'].create({
            'name': 'Visit Tower A', 'project_id': project.id,
            'partner_id': site.id})
        self.assertEqual(task.aabaan_area, 'Al Nuaimiya')
        site.aabaan_area = 'Al Rashidiya 2'
        self.assertEqual(task.aabaan_area, 'Al Rashidiya 2')

        product = self.env['product.product'].create({
            'name': 'Sites AMC (test)', 'type': 'service',
            'list_price': 100.0})
        order = self.env['sale.order'].create({
            'partner_id': client.id,
            'partner_shipping_id': site.id,
            'order_line': [(0, 0, {'product_id': product.id,
                                   'product_uom_qty': 1})],
        })
        self.assertEqual(order.aabaan_site_area, 'Al Rashidiya 2')

    def test_site_address_relabel(self):
        # Studio may override the label on a live database — accept any
        # site-flavoured label, reject only the old "Delivery Address".
        order_fields = self.env['sale.order'].fields_get(
            ['partner_shipping_id'], ['string'])
        self.assertIn('Site', order_fields['partner_shipping_id']['string'])
        move_fields = self.env['account.move'].fields_get(
            ['partner_shipping_id'], ['string'])
        if move_fields.get('partner_shipping_id'):
            self.assertIn(
                'Site', move_fields['partner_shipping_id']['string'])

    def test_studio_site_field_gets_domain(self):
        from odoo.addons.aabaan_client_sites import (
            SITE_DOMAIN, _configure_studio_site_fields)
        model = self.env['ir.model']._get('sale.order')
        field = self.env['ir.model.fields'].create({
            'model_id': model.id, 'name': 'x_test_site_premises',
            'ttype': 'many2one', 'relation': 'res.partner',
            'field_description': 'Site / Premises (test)',
            'state': 'manual',
        })
        _configure_studio_site_fields(self.env)
        self.assertEqual(field.domain, SITE_DOMAIN)
        # a deliberate configuration is never overwritten
        field.domain = "[('is_company', '=', False)]"
        _configure_studio_site_fields(self.env)
        self.assertEqual(field.domain, "[('is_company', '=', False)]")
