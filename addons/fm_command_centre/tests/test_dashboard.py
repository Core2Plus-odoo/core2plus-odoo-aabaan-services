# -*- coding: utf-8 -*-
from datetime import date

from odoo import fields
from odoo.addons.fm_command_centre.models.classification import (
    guess_emirate, guess_service)
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCeoDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env['fm.command.centre'])
        cls.branch = cls.env['fm.branch'].create({
            'name': 'Aabaan Services — Testville', 'emirate': 'ajman',
            'amc_monthly_target': 1000.0, 'cash_monthly_target': 500.0})
        cls.cash_product = cls.env['product.product'].create({
            'name': 'Pest Control Cash Work Test', 'type': 'service'})
        cls.amc_product = cls.env['product.product'].create({
            'name': 'Water Tank Cleaning Contract Test', 'type': 'service'})
        cls.walk_in = cls.env['res.partner'].create({'name': 'Walk-in Test'})

    def _invoice(self, product, price, partner=None):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': (partner or self.walk_in).id,
            'invoice_date': self.today,
            'branch_id': self.branch.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id, 'quantity': 1, 'price_unit': price,
                'tax_ids': [(6, 0, [])]})],
        })
        return move

    def test_keyword_guesses(self):
        self.assertEqual(guess_service('PEST CONTROL ATTESTATION'), 'lab')
        self.assertEqual(guess_service('100003: Anti Termites Treatment - Ajman'), 'termite')
        self.assertEqual(guess_service('Water Tank Cleaning Contract Ajman'), 'tank')
        self.assertEqual(guess_service('SOFA CLEANING'), 'sofa')
        self.assertEqual(guess_service('Pest Control Cash Work'), 'pest')
        self.assertEqual(guess_emirate('100017: Pest Control - Fujerah'), 'fujairah')
        self.assertEqual(guess_emirate('DUBAI, U.A.E'), 'dubai')
        self.assertFalse(guess_emirate('Cleaning Service'))

    def test_product_stream_from_name(self):
        self.assertEqual(self.cash_product.product_tmpl_id.fm_cc_stream, 'cash')
        self.assertEqual(self.amc_product.product_tmpl_id.fm_cc_stream, 'amc')
        self.assertEqual(self.amc_product.product_tmpl_id.fm_cc_service, 'tank')

    def test_invoice_stream_and_branch(self):
        cash = self._invoice(self.cash_product, 300)
        amc = self._invoice(self.amc_product, 700)
        self.assertEqual(cash.fm_cc_stream, 'cash')
        self.assertEqual(amc.fm_cc_stream, 'amc')
        self.assertEqual(cash.fm_cc_branch_id, self.branch)
        # manual correction sticks
        cash.fm_cc_stream = 'amc'
        self.assertEqual(cash.fm_cc_stream, 'amc')

    def test_dashboard_counts_the_month(self):
        Dash = self.env['fm.command.centre']
        before = Dash.get_data(self.today.strftime('%Y-%m'), True)
        self._invoice(self.cash_product, 300)
        self._invoice(self.amc_product, 700)
        after = Dash.get_data(self.today.strftime('%Y-%m'), True)
        self.assertAlmostEqual(after['cover']['cash'] - before['cover']['cash'], 300)
        self.assertAlmostEqual(after['cover']['amc'] - before['cover']['amc'], 700)
        self.assertEqual(after['cash']['jobs'] - before['cash']['jobs'], 1)
        row = next(r for r in after['scorecard']['rows'] if r['id'] == self.branch.id)
        self.assertAlmostEqual(row['total'], 1000)
        self.assertEqual(row['achieved'], 67.0)
        # drafts excluded when asked
        posted_only = Dash.get_data(self.today.strftime('%Y-%m'), False)
        row = next(r for r in posted_only['scorecard']['rows'] if r['id'] == self.branch.id)
        self.assertEqual(row['total'], 0)

    def test_every_section_present_on_any_month(self):
        Dash = self.env['fm.command.centre']
        for month in (False, '2020-01', 'not-a-month', date.today().strftime('%Y-%m')):
            data = Dash.get_data(month, True)
            for key in ('cover', 'versus', 'amc', 'cash', 'scorecard', 'services',
                        'credit', 'sales', 'expenses', 'bank'):
                self.assertIn(key, data)
            self.assertEqual(len(data['versus']['months']), 12)
            self.assertEqual(len(data['amc']['chart']), 12)
            self.assertEqual(len(data['credit']['aging']), 4)

    def test_pct_and_delta_never_invent_a_baseline(self):
        Dash = self.env['fm.command.centre']
        self.assertIsNone(Dash._pct(3, 0))
        self.assertIsNone(Dash._delta(5, 0))
        self.assertEqual(Dash._delta(150, 100), 50.0)

    def test_compact_variant_skips_services(self):
        data = self.env['fm.command.centre'].get_data(False, True, 'compact')
        self.assertEqual(data['services']['rows'], [])
        self.assertIn('credit', data)

    def test_service_filter_partitions_revenue(self):
        """Every invoice belongs to one service, so the services add up to
        the unfiltered total."""
        Dash = self.env['fm.command.centre']
        self._invoice(self.cash_product, 300)
        self._invoice(self.amc_product, 700)
        month = self.today.strftime('%Y-%m')
        whole = Dash.get_data(month, True)
        self.assertTrue(whole['service_options'])
        parts = sum(Dash.get_data(month, True, 'full', o['key'])['cover']['total']
                    for o in whole['service_options'])
        self.assertAlmostEqual(parts, whole['cover']['total'], places=2)
        tank = Dash.get_data(month, True, 'full', 'tank')
        self.assertEqual(tank['service'], 'tank')
        self.assertFalse(Dash.get_data(month, True, 'full', 'nope')['service'])

    def test_branch_filter_partitions_revenue(self):
        Dash = self.env['fm.command.centre']
        self._invoice(self.cash_product, 300)
        month = self.today.strftime('%Y-%m')
        whole = Dash.get_data(month, True)
        self.assertTrue(whole['branch_options'])
        mine = Dash.get_data(month, True, 'full', False, self.branch.id)
        self.assertEqual(mine['branch'], self.branch.id)
        self.assertEqual([r['id'] for r in mine['scorecard']['rows']], [self.branch.id])
        self.assertAlmostEqual(mine['cover']['total'], 300)
        self.assertFalse(Dash.get_data(month, True, 'full', False, -1)['branch'])
