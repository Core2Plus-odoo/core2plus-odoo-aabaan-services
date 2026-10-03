# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPricingGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Guard Test Co'})
        cls.priced = cls.env['product.product'].create({
            'name': 'Pest Control — Residential', 'type': 'service',
            'list_price': 250.0})
        # the catalogue's legacy duplicate: same service, no price
        cls.zero = cls.env['product.product'].create({
            'name': 'AAB-PEST', 'type': 'service', 'list_price': 0.0})

    def _order(self, product, **line_vals):
        vals = {'product_id': product.id, 'product_uom_qty': 1}
        vals.update(line_vals)
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, vals)],
        })

    def test_zero_priced_product_blocks_confirmation(self):
        order = self._order(self.zero)
        with self.assertRaises(UserError) as caught:
            order.action_confirm()
        message = str(caught.exception)
        self.assertIn('AAB-PEST', message,
                      "the message must name the offending line")
        self.assertIn('Intentionally Free', message,
                      "the message must state the way out, not just refuse")
        self.assertNotEqual(order.state, 'sale')

    def test_priced_product_confirms_normally(self):
        order = self._order(self.priced)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_full_discount_is_caught_too(self):
        """A 100% discount underbills exactly like an AED 0 product, so the
        guard measures the subtotal rather than the unit price."""
        order = self._order(self.priced, discount=100.0)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_intentionally_free_line_confirms_with_a_reason(self):
        order = self._order(
            self.zero, aabaan_free_ok=True,
            aabaan_free_reason='Free follow-up — 3-day rule')
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_intentionally_free_without_a_reason_is_refused(self):
        """Ticking the box must not become a silent bypass — a line that
        bills nothing has to be explainable later."""
        order = self._order(self.zero, aabaan_free_ok=True)
        with self.assertRaises(UserError) as caught:
            order.action_confirm()
        self.assertIn('reason', str(caught.exception).lower())
        self.assertNotEqual(order.state, 'sale')

    def test_zero_quantity_line_is_not_treated_as_underbilling(self):
        order = self._order(self.priced, product_uom_qty=0)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_section_and_note_lines_are_ignored(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'display_type': 'line_section', 'name': 'Services'}),
                (0, 0, {'display_type': 'line_note', 'name': 'Scope note'}),
                (0, 0, {'product_id': self.priced.id, 'product_uom_qty': 1}),
            ],
        })
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_usage_count_distinguishes_safe_to_archive(self):
        template = self.zero.product_tmpl_id
        template.invalidate_recordset()
        self.assertEqual(template.aabaan_line_usage, 0,
                         "unused zero-priced product — safe to archive")
        order = self._order(
            self.zero, aabaan_free_ok=True, aabaan_free_reason='Goodwill')
        template.invalidate_recordset()
        self.assertEqual(template.aabaan_line_usage, 1)
        self.assertEqual(template.aabaan_confirmed_usage, 0)
        order.action_confirm()
        template.invalidate_recordset()
        self.assertEqual(template.aabaan_confirmed_usage, 1,
                         "in use on a confirmed order — fix the price, "
                         "do not archive")
