# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDataEnrichment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._manual_field('sale.order', 'x_emirate_regime', 'selection', [
            ('dubai', 'Dubai'), ('sharjah', 'Sharjah'), ('ajman', 'Ajman'),
            ('quwain', 'Umm Al Quwain'), ('khaimah', 'Ras Al Khaimah')])
        cls.product = cls.env['product.product'].create({
            'name': 'Enrich AMC (test)', 'type': 'service',
            'list_price': 100.0})

    @classmethod
    def _manual_field(cls, model_name, name, ttype, selection=None):
        IrModelFields = cls.env['ir.model.fields']
        model = cls.env['ir.model']._get(model_name)
        if IrModelFields.search_count(
                [('model_id', '=', model.id), ('name', '=', name)]):
            return
        vals = {
            'model_id': model.id,
            'name': name,
            'ttype': ttype,
            'field_description': name,
            'state': 'manual',
        }
        if selection:
            vals['selection_ids'] = [
                (0, 0, {'value': value, 'name': label, 'sequence': seq})
                for seq, (value, label) in enumerate(selection)
            ]
        IrModelFields.create(vals)

    def _order_for(self, partner):
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id,
                                   'product_uom_qty': 1})],
        })

    def test_contract_tagged_from_customer_city(self):
        partner = self.env['res.partner'].create({
            'name': 'Enrich City Co', 'city': 'Ajman'})
        order = self._order_for(partner)
        self.env['sale.order'].aabaan_tag_emirates()
        self.assertEqual(order['x_emirate_regime'], 'ajman')

    def test_contract_tagged_from_customer_name(self):
        partner = self.env['res.partner'].create({
            'name': 'Blue Dubai Cafeteria LLC'})
        order = self._order_for(partner)
        self.env['sale.order'].aabaan_tag_emirates()
        self.assertEqual(order['x_emirate_regime'], 'dubai')

    def test_no_evidence_stays_untagged_and_no_overwrite(self):
        partner = self.env['res.partner'].create({'name': 'Neutral Trading'})
        order = self._order_for(partner)
        tagged_order = self._order_for(partner)
        tagged_order.write({'x_emirate_regime': 'sharjah'})
        self.env['sale.order'].aabaan_tag_emirates()
        self.assertFalse(order['x_emirate_regime'])
        self.assertEqual(tagged_order['x_emirate_regime'], 'sharjah')

    def test_contact_enrichment(self):
        partner = self.env['res.partner'].create({
            'name': 'Sunrise Cafeteria LLC', 'city': 'Ajman',
            'customer_rank': 1})
        self.env['res.partner'].aabaan_enrich_contacts()
        country = self.env.ref('base.ae', raise_if_not_found=False)
        if country:
            self.assertEqual(partner.country_id, country)
            self.assertIn('ajman', (partner.state_id.name or '').casefold())
        has_food = self.env['res.partner.industry'].search(
            [('name', 'ilike', 'food')], limit=1)
        if has_food:
            self.assertEqual(partner.industry_id, has_food)

    def test_contact_state_from_tagged_contract(self):
        partner = self.env['res.partner'].create({
            'name': 'Plain Name Co', 'customer_rank': 1})
        order = self._order_for(partner)
        order.write({'x_emirate_regime': 'sharjah'})
        self.env['res.partner'].aabaan_enrich_contacts()
        if self.env.ref('base.ae', raise_if_not_found=False):
            self.assertIn('sharjah', (partner.state_id.name or '').casefold())
