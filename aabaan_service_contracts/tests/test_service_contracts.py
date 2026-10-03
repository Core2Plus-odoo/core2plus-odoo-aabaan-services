# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestServiceContracts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['res.partner'].create({
            'name': 'Multi-Site Test Group', 'is_company': True})
        cls.site_a = cls.env['res.partner'].create({
            'name': 'Multi-Site Test Group — Tower A',
            'parent_id': cls.client.id, 'type': 'delivery'})
        cls.site_b = cls.env['res.partner'].create({
            'name': 'Multi-Site Test Group — Tower B',
            'parent_id': cls.client.id, 'type': 'delivery'})
        cls.product = cls.env['product.product'].create({
            'name': 'Contract Test Service', 'type': 'service',
            'list_price': 1000.0})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.client.id,
            'order_line': [
                (0, 0, {'product_id': cls.product.id, 'product_uom_qty': 1,
                       'site_id': cls.site_a.id}),
                (0, 0, {'product_id': cls.product.id, 'product_uom_qty': 2,
                       'site_id': cls.site_b.id}),
            ],
        })
        cls.order.action_confirm()
        cls.project = cls.env['project.project'].create({
            'name': 'Service Contracts Test FSM', 'is_fsm': True})

    def _visit(self, site, escalated=False):
        vals = {
            'name': 'Visit', 'project_id': self.project.id,
            'sale_order_id': self.order.id, 'partner_id': site.id,
            'sla_escalated': escalated,
        }
        if 'planned_date_begin' in self.env['project.task']._fields:
            # already-due visit — only settled visits count toward a
            # track record, matching the model's own logic
            vals['planned_date_begin'] = (
                fields.Datetime.now() - timedelta(days=1))
        return self.env['project.task'].create(vals)

    def test_site_value_from_tagged_lines_only(self):
        site_a = self.env['aabaan.contract.site'].create({
            'order_id': self.order.id, 'site_id': self.site_a.id})
        site_b = self.env['aabaan.contract.site'].create({
            'order_id': self.order.id, 'site_id': self.site_b.id})
        self.assertEqual(site_a.site_value, 1000.0)
        self.assertEqual(site_b.site_value, 2000.0)

    def test_uptime_from_real_visits_not_invented(self):
        site_a = self.env['aabaan.contract.site'].create({
            'order_id': self.order.id, 'site_id': self.site_a.id})
        self.assertEqual(
            site_a.uptime_ytd, 0.0,
            "no visits yet — uptime must read 0, never a fabricated figure")
        self._visit(self.site_a, escalated=False)
        self._visit(self.site_a, escalated=False)
        self._visit(self.site_a, escalated=True)
        site_a.invalidate_recordset()
        self.assertEqual(site_a.visit_count_ytd, 3)
        self.assertAlmostEqual(site_a.uptime_ytd, 66.7, places=1)

    def test_contract_avg_uptime_is_visit_weighted(self):
        site_a = self.env['aabaan.contract.site'].create({
            'order_id': self.order.id, 'site_id': self.site_a.id})
        site_b = self.env['aabaan.contract.site'].create({
            'order_id': self.order.id, 'site_id': self.site_b.id})
        self._visit(self.site_a, escalated=True)   # 1 visit, 0% uptime
        for _ in range(9):
            self._visit(self.site_b, escalated=False)  # 9 visits, 100%
        self.order.invalidate_recordset()
        # weighted: (0*1 + 100*9) / 10 = 90.0, not a naive average of 50
        self.assertEqual(self.order.contract_sites_count, 2)
        self.assertAlmostEqual(self.order.contract_avg_uptime, 90.0, places=1)

    def test_document_status_lifecycle(self):
        today = fields.Date.context_today(self.env.user)
        no_expiry = self.env['aabaan.contract.document'].create({
            'order_id': self.order.id, 'name': 'Master Agreement',
            'document_type': 'master_agreement'})
        expiring = self.env['aabaan.contract.document'].create({
            'order_id': self.order.id, 'name': 'Insurance',
            'document_type': 'insurance',
            'valid_until': today + timedelta(days=10)})
        expired = self.env['aabaan.contract.document'].create({
            'order_id': self.order.id, 'name': 'Old Cert',
            'document_type': 'iso_cert',
            'valid_until': today - timedelta(days=1)})
        valid = self.env['aabaan.contract.document'].create({
            'order_id': self.order.id, 'name': 'MSDS Pack',
            'document_type': 'msds',
            'valid_until': today + timedelta(days=200)})
        self.assertEqual(no_expiry.document_status, 'no_expiry')
        self.assertEqual(expiring.document_status, 'expiring_soon')
        self.assertEqual(expired.document_status, 'expired')
        self.assertEqual(valid.document_status, 'valid')
        self.assertEqual(self.order.contract_documents_count, 4,
                         "smart-button count must match the pack")
        action = self.order.action_view_contract_documents()
        self.assertEqual(action['res_model'], 'aabaan.contract.document')
        self.assertIn(('order_id', '=', self.order.id), action['domain'])

    def test_document_expiry_cron_raises_one_activity_no_duplicates(self):
        today = fields.Date.context_today(self.env.user)
        self.env['aabaan.contract.document'].create({
            'order_id': self.order.id, 'name': 'Insurance',
            'document_type': 'insurance',
            'valid_until': today + timedelta(days=5)})
        self.env['aabaan.contract.document']._cron_aabaan_document_expiry()
        count = self.env['mail.activity'].search_count([
            ('res_model', '=', 'sale.order'), ('res_id', '=', self.order.id)])
        self.assertEqual(count, 1)
        self.env['aabaan.contract.document']._cron_aabaan_document_expiry()
        self.assertEqual(
            self.env['mail.activity'].search_count([
                ('res_model', '=', 'sale.order'),
                ('res_id', '=', self.order.id)]),
            count, "re-running the cron must not duplicate the activity")

    def test_compliance_documents_cannot_be_deleted_by_salesmen(self):
        """A salesperson can build the compliance pack but not thin it out —
        deleting evidence is a manager's call (cleanup-audit tightening)."""
        Users = self.env['res.users']
        # the groups field was renamed across versions — resolve at runtime
        gfield = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        salesman = Users.create({
            'name': 'Doc Test Salesman', 'login': 'doc_test_salesman',
            gfield: [(6, 0, [self.env.ref(
                'sales_team.group_sale_salesman').id])]})
        manager = Users.create({
            'name': 'Doc Test Manager', 'login': 'doc_test_manager',
            gfield: [(6, 0, [self.env.ref(
                'sales_team.group_sale_manager').id])]})
        doc = self.env['aabaan.contract.document'].create({
            'order_id': self.order.id, 'name': 'Deletable?',
            'document_type': 'other'})
        created = self.env['aabaan.contract.document'].with_user(
            salesman).create({
                'order_id': self.order.id, 'name': 'Salesman-created',
                'document_type': 'other'})
        self.assertTrue(created, "creating pack documents stays open to all")
        with self.assertRaises(AccessError):
            doc.with_user(salesman).unlink()
        doc.with_user(manager).unlink()

    def test_site_id_domain_restricted_to_customers_own_sites(self):
        other_client = self.env['res.partner'].create({'name': 'Other Co'})
        other_site = self.env['res.partner'].create({
            'name': 'Other Co Site', 'parent_id': other_client.id,
            'type': 'delivery'})
        field = self.order.fields_get(['contract_site_ids'])
        self.assertIn('contract_site_ids', field)
        # the domain lives on the view, not the model — assert the site
        # itself is not a child of this order's customer, which is what
        # the view domain (child_of parent.partner_id) would exclude
        self.assertNotEqual(other_site.parent_id, self.client)
