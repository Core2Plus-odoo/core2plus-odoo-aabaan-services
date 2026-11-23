# -*- coding: utf-8 -*-
"""The customer portal pages.

The rule is tested from both sides on purpose: a portal rule that lets the
customer see their own visits also passes a test written against a rule
that lets everybody see everything. Only the other company's visit, which
must stay hidden, tells the two apart.
"""
from datetime import timedelta

from odoo import fields, http
from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestFmPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Portal Test Towers LLC", "is_company": True})
        cls.other = cls.env["res.partner"].create({
            "name": "Someone Else Trading", "is_company": True})
        cls.portal_user = new_test_user(
            cls.env, login="fm_portal_customer", groups="base.group_portal",
            name="Site Manager", email="manager@towers.example")
        cls.portal_user.partner_id.parent_id = cls.customer
        project = cls.env["project.project"].search([("is_fsm", "=", True)], limit=1)
        now = fields.Datetime.now()

        def visit(name, partner, days, **vals):
            return cls.env["project.task"].create(dict({
                "name": name, "project_id": project.id, "partner_id": partner.id,
                "planned_date_begin": now + timedelta(days=days),
                "date_deadline": now + timedelta(days=days, hours=2),
            }, **vals))

        cls.upcoming = visit("FMP upcoming visit", cls.customer, 5)
        cls.done = visit("FMP completed visit", cls.customer, -5, state="1_done")
        cls.foreign = visit("FMP foreign visit", cls.other, 5)

    def test_rule_opens_own_visits_only(self):
        Task = self.env["project.task"].with_user(self.portal_user)
        visible = Task.search([("name", "like", "FMP ")])
        self.assertIn(self.upcoming, visible)
        self.assertIn(self.done, visible)
        self.assertNotIn(self.foreign, visible)

    def test_jobs_page(self):
        self.authenticate("fm_portal_customer", "fm_portal_customer")
        html = self.url_open("/my/jobs").text
        self.assertIn("FMP upcoming visit", html)
        self.assertNotIn("FMP completed visit", html)
        self.assertNotIn("FMP foreign visit", html)
        html = self.url_open("/my/jobs?filterby=done").text
        self.assertIn("FMP completed visit", html)

    def test_documents_page_lists_service_reports(self):
        self.authenticate("fm_portal_customer", "fm_portal_customer")
        html = self.url_open("/my/fm-documents").text
        self.assertIn("FMP completed visit", html)
        self.assertNotIn("FMP foreign visit", html)

    def test_service_request_creates_lead(self):
        self.authenticate("fm_portal_customer", "fm_portal_customer")
        self.assertEqual(self.url_open("/my/service-request").status_code, 200)
        response = self.url_open("/my/service-request", data={
            "csrf_token": http.Request.csrf_token(self),
            "service": "pest",
            "site": "Tower B, 4th floor",
            "description": "Cockroaches in the kitchen",
        })
        self.assertEqual(response.status_code, 200)
        lead = self.env["crm.lead"].search([("partner_id", "=", self.portal_user.partner_id.id)])
        self.assertEqual(len(lead), 1)
        self.assertIn("Pest Control", lead.name)
        self.assertIn("Cockroaches in the kitchen", lead.description)
        self.assertIn("Tower B, 4th floor", lead.description)

    def test_service_request_needs_a_service(self):
        self.authenticate("fm_portal_customer", "fm_portal_customer")
        self.url_open("/my/service-request", data={
            "csrf_token": http.Request.csrf_token(self), "service": "", "description": "x"})
        self.assertFalse(self.env["crm.lead"].search(
            [("partner_id", "=", self.portal_user.partner_id.id)]))

    def test_home_shows_cards(self):
        self.authenticate("fm_portal_customer", "fm_portal_customer")
        html = self.url_open("/my/home").text
        for url in ("/my/jobs", "/my/fm-documents", "/my/service-request"):
            self.assertIn(url, html)

    def test_service_report_downloads_without_timesheets(self):
        """Odoo's own report raises on a visit with no timesheet, product or
        worksheet; the portal must still hand the customer a PDF."""
        self.authenticate("fm_portal_customer", "fm_portal_customer")
        response = self.url_open(f"/my/jobs/{self.done.id}/report")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/pdf")
        # Neither another company's visit nor one not yet done.
        for task in (self.foreign, self.upcoming):
            response = self.url_open(f"/my/jobs/{task.id}/report")
            self.assertNotEqual(response.headers.get("Content-Type"), "application/pdf")
