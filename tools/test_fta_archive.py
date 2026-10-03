#!/usr/bin/env python3
"""Tests for the FTA archive extractor.

Plain unittest, not an Odoo test: fta_archive.py is a standalone tool that
talks to an Odoo instance over XML-RPC, so it must be testable without an
Odoo installation. Run it before every use against a real database:

    python3 tools/test_fta_archive.py

The read-only guarantee is the only thing standing between this script and
a database that must never be written to, so it is tested rather than
assumed.
"""
import importlib.util
import os
import unittest
import xmlrpc.client


class FakeProxy:
    """Records what would have been sent, so a leak is detectable."""
    sent = []

    def __init__(self, url, allow_none=None):
        self.url = url

    def authenticate(self, db, login, key, ctx):
        return 0 if login == 'wrong' else 7

    def execute_kw(self, db, uid, key, model, method, args, kwargs):
        FakeProxy.sent.append((model, method))
        return []


def _load():
    xmlrpc.client.ServerProxy = FakeProxy
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'fta_archive.py')
    spec = importlib.util.spec_from_file_location('fta_archive', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fta = _load()

# Everything that must never reach a read-only database. _render_qweb_pdf is
# in here deliberately: rendering an Odoo invoice report can store an
# ir.attachment, which is a write.
MUTATING = [
    'create', 'write', 'unlink', 'copy', 'action_post', 'button_draft',
    'message_post', 'action_invoice_sent', '_render_qweb_pdf',
    'execute_kw', 'load', 'import_data', 'toggle_active',
]


class TestReadOnlyEnforcement(unittest.TestCase):

    def setUp(self):
        FakeProxy.sent = []
        self.api = fta.ReadOnly('https://example.odoo.com', 'legacy', 'u', 'k')

    def test_reads_are_allowed(self):
        self.api('account.move', 'search', [])
        self.api('account.move', 'read', [1], fields=['name'])
        self.assertEqual(
            FakeProxy.sent,
            [('account.move', 'search'), ('account.move', 'read')])

    def test_every_mutating_method_is_refused(self):
        for method in MUTATING:
            with self.subTest(method=method):
                with self.assertRaises(fta.ReadOnlyViolation):
                    self.api('account.move', method, [1])

    def test_refusal_happens_before_the_network_call(self):
        """The guarantee is that nothing is SENT — not that the server
        happened to reject it."""
        for method in MUTATING:
            with self.subTest(method=method):
                FakeProxy.sent = []
                with self.assertRaises(fta.ReadOnlyViolation):
                    self.api('account.move', method, [1])
                self.assertEqual(
                    FakeProxy.sent, [],
                    "%s reached the network before being refused" % method)

    def test_refusal_explains_itself(self):
        with self.assertRaises(fta.ReadOnlyViolation) as caught:
            self.api('account.move', 'write', [1], {'name': 'x'})
        message = str(caught.exception)
        self.assertIn('read-only', message)
        self.assertIn('never be written', message)
        self.assertIn('write', message)

    def test_whitelist_contains_no_mutating_method(self):
        for method in MUTATING:
            self.assertNotIn(method, fta.READ_ONLY_METHODS)

    def test_failed_authentication_stops_immediately(self):
        with self.assertRaises(SystemExit):
            fta.ReadOnly('https://example.odoo.com', 'legacy', 'wrong', 'k')


class TestNormalisation(unittest.TestCase):
    """The archive has to be readable in seven years without Odoo around to
    interpret it, so many2one pairs and False become plain JSON."""

    def test_many2one_becomes_id_and_name(self):
        self.assertEqual(fta.flatten([3, 'Acme']), {'id': 3, 'name': 'Acme'})

    def test_false_becomes_null(self):
        self.assertIsNone(fta.flatten(False))
        self.assertIsNone(fta.flatten(None))

    def test_scalars_pass_through(self):
        self.assertEqual(fta.flatten('text'), 'text')
        self.assertEqual(fta.flatten(12.5), 12.5)
        self.assertEqual(fta.flatten([1, 2, 3]), [1, 2, 3])

    def test_clean_normalises_a_whole_record(self):
        self.assertEqual(
            fta.clean({'partner_id': [3, 'Acme'], 'ref': False, 'n': 2}),
            {'partner_id': {'id': 3, 'name': 'Acme'}, 'ref': None, 'n': 2})

    def test_sha256_is_stable(self):
        self.assertEqual(fta.sha256(b'abc'), fta.sha256(b'abc'))
        self.assertNotEqual(fta.sha256(b'abc'), fta.sha256(b'abd'))


class TestRetentionPolicy(unittest.TestCase):

    def test_seven_years_not_five(self):
        """Corporate Tax (FDL 47/2022 art. 56) requires 7 years; the VAT
        5-year period is a floor. A 5-year archive would under-retain."""
        self.assertEqual(fta.RETENTION_YEARS, 7)

    def test_mandatory_invoice_particulars_are_exported(self):
        """Retaining information instead of the original document is only
        permitted if every mandatory particular survives."""
        for field in ('name', 'invoice_date', 'partner_id', 'company_id',
                      'currency_id', 'amount_untaxed', 'amount_tax',
                      'amount_total', 'delivery_date'):
            self.assertIn(field, fta.INVOICE_FIELDS)
        for field in ('name', 'quantity', 'price_unit', 'discount',
                      'price_subtotal', 'tax_ids'):
            self.assertIn(field, fta.LINE_FIELDS)
        self.assertIn('vat', fta.PARTNER_FIELDS)
        self.assertIn('vat', fta.COMPANY_FIELDS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
