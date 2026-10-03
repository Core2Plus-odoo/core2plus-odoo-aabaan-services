# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestServiceDocuments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'Docs Test FSM', 'is_fsm': True})
        cls.partner = cls.env['res.partner'].create({'name': 'Docs Test Co'})
        cls.task = cls.env['project.task'].create({
            'name': 'Water tank cleaning — Docs Test',
            'project_id': cls.project.id,
            'partner_id': cls.partner.id,
        })

    def test_service_report_renders_as_draft(self):
        html = self.env['ir.actions.report']._render_qweb_html(
            'aabaan_service_reports.report_visit_service', self.task.ids)[0]
        self.assertIn(b'Service Report', html)
        self.assertIn(b'DRAFT', html)

    def test_certificate_blocked_until_completed(self):
        with self.assertRaises(UserError):
            self.env['ir.actions.report']._render_qweb_html(
                'aabaan_service_reports.report_tank_certificate',
                self.task.ids)

    def test_certificate_blocked_for_wrong_kind(self):
        self.task.write({'visit_completed_at': fields.Datetime.now()})
        with self.assertRaises(UserError):
            self.env['ir.actions.report']._render_qweb_html(
                'aabaan_service_reports.report_termite_warranty',
                self.task.ids)

    def test_tank_certificate_renders_when_eligible(self):
        self.task.write({
            'visit_completed_at': fields.Datetime.now(),
            'treatment_summary': 'Drained, scrubbed, disinfected, refilled.',
        })
        html = self.env['ir.actions.report']._render_qweb_html(
            'aabaan_service_reports.report_tank_certificate', self.task.ids)[0]
        self.assertIn(b'CLEANING', html)
        self.assertIn(b'Docs Test Co', html)
