# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFinanceCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Plan = cls.env['account.analytic.plan']
        cls.emirate_plan = Plan.search([('name', 'ilike', 'emirate')], limit=1) \
            or Plan.create({'name': 'Emirate'})
        cls.service_plan = Plan.search([('name', 'ilike', 'service')], limit=1) \
            or Plan.create({'name': 'Service Line'})
        Acc = cls.env['account.analytic.account']
        cls.aa_ajman = Acc.search([('root_plan_id', '=', cls.emirate_plan.id),
                                   ('name', 'ilike', 'ajman')], limit=1) \
            or Acc.create({'name': 'Ajman', 'plan_id': cls.emirate_plan.id})
        cls.aa_pest = Acc.search([('root_plan_id', '=', cls.service_plan.id),
                                  ('name', 'ilike', 'pest')], limit=1) \
            or Acc.create({'name': 'Pest Control', 'plan_id': cls.service_plan.id})
        cls.partner = cls.env['res.partner'].create({'name': 'Recovery Test Co'})

    def _invoice(self, due, tagged_line=True, post_ctx=None):
        dist = {}
        if tagged_line:
            dist = {str(self.aa_ajman.id): 100, str(self.aa_pest.id): 100}
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-08-05',
            'invoice_date_due': due,
            'invoice_line_ids': [(0, 0, {
                'name': 'AMC instalment', 'quantity': 1, 'price_unit': 1000,
                'analytic_distribution': dist or False,
            })],
        })
        move.with_context(**(post_ctx or {})).action_post()
        return move

    @freeze_time('2026-08-10')
    def test_recovery_buckets(self):
        prev = self._invoice('2026-07-15')
        curr = self._invoice('2026-08-20')
        futu = self._invoice('2026-10-01')
        self.assertEqual(prev.recovery_bucket, 'previous')
        self.assertEqual(curr.recovery_bucket, 'current')
        self.assertEqual(futu.recovery_bucket, 'future')
        self.env['account.move']._cron_refresh_recovery_buckets()

    @freeze_time('2026-08-10')
    def test_analytic_enforcement(self):
        with self.assertRaises(UserError,
                               msg="untagged invoice line must not post"):
            self._invoice('2026-08-20', tagged_line=False)
        ok = self._invoice('2026-08-20', tagged_line=True)
        self.assertEqual(ok.state, 'posted')
        bypass = self._invoice('2026-08-25', tagged_line=False,
                               post_ctx={'aabaan_skip_analytic_check': True})
        self.assertEqual(bypass.state, 'posted')

    @freeze_time('2026-08-10')
    def test_vendor_bill_requires_branch_only(self):
        def bill(dist):
            move = self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': self.partner.id,
                'invoice_date': '2026-08-05',
                'invoice_line_ids': [(0, 0, {
                    'name': 'Office utilities', 'quantity': 1,
                    'price_unit': 500,
                    'analytic_distribution': dist or False,
                })],
            })
            move.action_post()
            return move
        with self.assertRaises(UserError,
                               msg="untagged bill must not post"):
            bill({})
        ok = bill({str(self.aa_ajman.id): 100})  # branch alone is enough
        self.assertEqual(ok.state, 'posted')

    def _expense_account(self):
        Account = self.env['account.account']
        account = Account.search([('account_type', '=', 'expense')], limit=1)
        if not account:
            self.skipTest("no chart of accounts on this database")
        return account

    def _entry(self, dist=None):
        """A payroll-shaped journal entry: an expense line and its balancing
        payable line, no analytic distribution unless one is given."""
        expense = self._expense_account()
        payable = self.env['account.account'].search(
            [('account_type', '=', 'liability_payable')], limit=1) \
            or self.env['account.account'].search(
                [('account_type', 'not like', 'expense%')], limit=1)
        if not payable:
            self.skipTest("no balancing account on this database")
        journal = self.env['account.journal'].search(
            [('type', '=', 'general')], limit=1)
        if not journal:
            self.skipTest("no general journal on this database")
        return self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2026-08-31',
            'ref': 'Payslip batch 08/2026',
            'line_ids': [
                (0, 0, {'name': 'Salaries', 'account_id': expense.id,
                        'debit': 5000, 'credit': 0,
                        'analytic_distribution': dist or False}),
                (0, 0, {'name': 'Salaries payable', 'account_id': payable.id,
                        'debit': 0, 'credit': 5000}),
            ],
        })

    def test_machine_entry_posts_and_is_flagged(self):
        """H1: blocking machine-written entries broke payroll, depreciation,
        COGS and reconciliation — none of which offer a screen to tag. They
        post now, and the flag is what keeps them from going unseen."""
        entry = self._entry()
        entry.action_post()
        self.assertEqual(entry.state, 'posted',
                         "an untagged journal entry must still post")
        self.assertTrue(entry.aabaan_analytic_incomplete,
                        "an untagged posted entry must be flagged")

    def test_tagging_an_entry_clears_the_flag(self):
        entry = self._entry()
        entry.action_post()
        self.assertTrue(entry.aabaan_analytic_incomplete)
        expense_line = entry.line_ids.filtered(
            lambda l: l.account_id.account_type == 'expense')
        expense_line.analytic_distribution = {str(self.aa_ajman.id): 100}
        self.assertFalse(entry.aabaan_analytic_incomplete,
                         "tagging the line must empty it from the queue")

    def test_tagged_entry_is_never_flagged(self):
        entry = self._entry(dist={str(self.aa_ajman.id): 100})
        entry.action_post()
        self.assertEqual(entry.state, 'posted')
        self.assertFalse(entry.aabaan_analytic_incomplete)

    @freeze_time('2026-08-10')
    def test_bypassed_invoice_is_flagged(self):
        """The escape hatch stops the block, not the visibility — an invoice
        posted with aabaan_skip_analytic_check still owes its branch."""
        move = self._invoice('2026-08-25', tagged_line=False,
                             post_ctx={'aabaan_skip_analytic_check': True})
        self.assertEqual(move.state, 'posted')
        self.assertTrue(move.aabaan_analytic_incomplete)

    def test_department_plan_seeded(self):
        self.assertTrue(self.env['account.analytic.plan'].search(
            [('name', 'ilike', 'department')], limit=1))
