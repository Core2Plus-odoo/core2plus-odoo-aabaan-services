# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestInvoiceReport(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.tax_5 = cls.env['account.tax'].create({
            'name': 'VAT 5%', 'amount': 5.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': cls.company_data['company'].id,
        })
        cls.move = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner_a.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Pest control — AMC',
                'quantity': 1, 'price_unit': 1000.0,
                'tax_ids': [(6, 0, cls.tax_5.ids)],
                'account_id': cls.company_data['default_account_revenue'].id,
            })],
        })

    def test_guard_blocks_non_customer_documents(self):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.partner_a.id,
        })
        with self.assertRaises(UserError):
            bill.aabaan_tax_invoice_guard()
        self.move.aabaan_tax_invoice_guard()  # must not raise

    def test_document_title(self):
        self.assertEqual(self.move._aabaan_document_title(), 'Tax Invoice')
        refund = self.move.copy({'move_type': 'out_refund'})
        self.assertEqual(refund._aabaan_document_title(), 'Tax Credit Note')

    def test_numbered_lines_skip_sections(self):
        self.move.write({'invoice_line_ids': [(0, 0, {
            'display_type': 'line_section', 'name': 'Services',
        })]})
        rows = self.move._aabaan_numbered_lines()
        numbered = [r for r in rows if r['no'] is not None]
        self.assertEqual(len(numbered), 1)
        sectioned = [r for r in rows if r['line'].display_type == 'line_section']
        self.assertEqual(sectioned[0]['no'], None)

    def test_audit_trail_created_then_posted(self):
        labels = [r['label'] for r in self.move._aabaan_audit_trail()]
        self.assertIn('Created', labels)
        self.assertNotIn('Posted', labels)
        self.move.action_post()
        labels = [r['label'] for r in self.move._aabaan_audit_trail()]
        self.assertIn('Posted', labels)

    def test_audit_trail_payment_received(self):
        self.move.action_post()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=self.move.ids).create({})
        wizard._create_payments()
        rows = [r for r in self.move._aabaan_audit_trail()
                if r['label'] == 'Payment received']
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]['amount'], 1050.0, places=2)

    def test_tax_lines_breakdown(self):
        self.move.action_post()
        lines = self.move._aabaan_tax_lines()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]['base'], 1000.0, places=2)
        self.assertAlmostEqual(lines[0]['amount'], 50.0, places=2)
        self.assertEqual(lines[0]['rate'], 5.0)

    def test_audit_trail_html_empty_before_posting(self):
        self.assertIn('Nothing to show yet', self.move.aabaan_audit_trail_html)
        self.move.action_post()
        self.assertIn('Posted', self.move.aabaan_audit_trail_html)
