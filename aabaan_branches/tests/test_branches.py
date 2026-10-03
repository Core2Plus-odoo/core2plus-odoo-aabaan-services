# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo.tests import TransactionCase, tagged

from odoo.addons.aabaan_branches import BRANCHES, _emirate_plan, _setup_branches


@tagged('post_install', '-at_install')
class TestBranches(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plan = _emirate_plan(cls.env)

    def _branch_by_licence(self, registry):
        return self.env['account.analytic.account'].sudo().with_context(
            active_test=False).search(
            [('aabaan_licence_no', '=', registry)], limit=1)

    def test_each_branch_carries_its_licence(self):
        if not self.plan:
            self.skipTest("no Emirate analytic plan in this database")
        for spec in BRANCHES:
            branch = self._branch_by_licence(spec['registry'])
            self.assertTrue(
                branch, f"no branch carries licence {spec['registry']}")
            self.assertEqual(
                str(branch.aabaan_licence_expiry), spec['licence_expiry'])
            self.assertEqual(
                branch.root_plan_id, self.plan,
                "a branch must sit on the Emirate analytic plan")

    def test_setup_is_idempotent(self):
        if not self.plan:
            self.skipTest("no Emirate analytic plan in this database")
        Analytic = self.env['account.analytic.account'].sudo().with_context(
            active_test=False)
        before = Analytic.search_count([('plan_id', 'child_of', self.plan.id)])
        _setup_branches(self.env)
        after = Analytic.search_count([('plan_id', 'child_of', self.plan.id)])
        self.assertEqual(before, after,
                         "re-running setup must not duplicate branches")

    def test_setup_creates_no_company(self):
        """The whole point of this version: branches, not legal entities."""
        Company = self.env['res.company'].sudo().with_context(
            active_test=False)
        before = Company.search_count([])
        _setup_branches(self.env)
        self.assertEqual(before, Company.search_count([]),
                         "branch setup must never create a company")

    def test_contract_branch_field_is_on_the_emirate_plan(self):
        if not self.plan:
            self.skipTest("no Emirate analytic plan in this database")
        field = self.env['sale.order']._fields.get('aabaan_branch_id')
        self.assertTrue(field, "contracts must offer a Branch field")
        self.assertEqual(field.comodel_name, 'account.analytic.account')

    def test_licence_cron_raises_one_activity_per_licence(self):
        Company = self.env['res.company']
        main = self.env.ref('base.main_company')
        before = self.env['mail.activity'].search_count([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', main.partner_id.id),
        ])
        Company._cron_aabaan_licence_expiry()
        first = self.env['mail.activity'].search_count([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', main.partner_id.id),
        ])
        Company._cron_aabaan_licence_expiry()
        second = self.env['mail.activity'].search_count([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', main.partner_id.id),
        ])
        self.assertGreaterEqual(first, before)
        self.assertEqual(first, second,
                         "an open renewal activity must block duplicates")
