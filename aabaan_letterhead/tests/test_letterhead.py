# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo.addons.aabaan_letterhead import tools
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLetterhead(TransactionCase):

    def test_templates_render(self):
        """HTML-render both shared templates the way a report would — a bad
        field reference fails here, not on the first customer print."""
        for ref in ('aabaan_letterhead.header', 'aabaan_letterhead.footer'):
            html = self.env['ir.qweb']._render(ref, {
                'company': self.env.company,
                'image_data_uri': lambda value: '',
            })
            self.assertIn('ab-plain', str(html))

    def test_footer_carries_the_compliance_identity(self):
        company = self.env.company
        company.vat = '104302919600003'
        company.company_registry = '103074'
        html = str(self.env['ir.qweb']._render('aabaan_letterhead.footer', {
            'company': company,
            'image_data_uri': lambda value: '',
        }))
        self.assertIn('104302919600003', html)
        self.assertIn('103074', html)
        self.assertIn('800 AABAN', html)

    def test_line_desc_strips_product_code_prefix_only(self):
        class Product:
            default_code = 'AAB-X'

        class Line:
            product_id = Product()

        line = Line()
        line.name = '[AAB-X] Deep Cleaning'
        self.assertEqual(tools.line_desc(line), 'Deep Cleaning')
        line.name = 'Deep Cleaning [AAB-X] inside'
        self.assertEqual(tools.line_desc(line), 'Deep Cleaning [AAB-X] inside')
        line.name = None
        self.assertEqual(tools.line_desc(line), '')

    def test_amount_in_words_never_raises(self):
        order_like = type('R', (), {})()
        order_like.currency_id = self.env.company.currency_id
        order_like.amount_total = 1050.0
        self.assertTrue(tools.amount_in_words(order_like))
        broken = type('R', (), {})()  # no fields at all
        self.assertEqual(tools.amount_in_words(broken), '')
