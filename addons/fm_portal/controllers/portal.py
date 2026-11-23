# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import _, fields, http
from odoo.fields import Domain
from odoo.http import request

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

# A visit in one of these states is behind the customer, whatever stage it
# sits in -- the FM stages are named per branch, the states are not.
CLOSED_STATES = ("1_done", "1_canceled")


class FmCustomerPortal(CustomerPortal):
    """The FM pages of the customer portal.

    Everything shown here belongs to the customer's *company*
    (commercial_partner_id), not the one login: a facility manager and the
    site supervisor of the same building see the same visits.
    """

    def _fm_customer(self):
        return request.env.user.partner_id.commercial_partner_id

    # ------------------------------------------------------------------
    # Home counters
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "fm_job_count" in counters:
            values["fm_job_count"] = request.env["project.task"].search_count(
                self._fm_jobs_domain("open"))
        if "fm_certificate_count" in counters:
            values["fm_certificate_count"] = (
                len(self._fm_certificates()) + len(self._fm_service_reports()))
        return values

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------
    def _fm_jobs_filters(self):
        now = fields.Datetime.now()
        return {
            "open": {"label": _("Current & Upcoming"),
                     "domain": [("state", "not in", CLOSED_STATES)]},
            "upcoming": {"label": _("Upcoming"),
                         "domain": [("state", "not in", CLOSED_STATES),
                                    ("planned_date_begin", ">", now)]},
            "current": {"label": _("Current"),
                        "domain": [("state", "not in", CLOSED_STATES),
                                   ("planned_date_begin", "<=", now)]},
            "done": {"label": _("Completed"),
                     "domain": [("state", "=", "1_done")]},
            "all": {"label": _("All"), "domain": []},
        }

    def _fm_jobs_domain(self, filterby="open"):
        """Searched as the portal user, so the portal rule in
        security/portal_rules.xml decides what is theirs; the partner
        clause only keeps another company's visits out should some other
        rule ever let them through."""
        flt = self._fm_jobs_filters().get(filterby) or self._fm_jobs_filters()["open"]
        return Domain.AND([
            [("is_fsm", "=", True),
             ("partner_id", "child_of", self._fm_customer().id)],
            flt["domain"],
        ])

    @staticmethod
    def _fm_job_service(job):
        """The service a visit is for, as its label.

        Rarely on the visit itself (20 of 3,902 on the database): it is the
        contract that knows, in fm_service_line or -- on most orders -- the
        Studio x_service_line, which no module declares and so is read only
        when present.
        """
        order = job.fm_contract_order_id or job.sale_order_id
        for record, name in ((job, "fm_service_line"), (order, "fm_service_line"),
                             (order, "x_service_line")):
            if record and name in record._fields and record[name]:
                field = record._fields[name]
                if field.type == "selection":
                    return dict(field._description_selection(record.env)).get(record[name], "")
                return record[name].display_name if field.type == "many2one" else record[name]
        return ""

    @http.route(["/my/jobs", "/my/jobs/page/<int:page>"], type="http", auth="user", website=True)
    def portal_my_fm_jobs(self, page=1, filterby="open", **kw):
        Task = request.env["project.task"]
        filters = self._fm_jobs_filters()
        if filterby not in filters:
            filterby = "open"
        domain = self._fm_jobs_domain(filterby)
        # Upcoming reads soonest first; anything already done, latest first.
        order = "planned_date_begin desc, id desc" if filterby in ("done", "all") \
            else "planned_date_begin asc, id asc"
        pager = portal_pager(
            url="/my/jobs", url_args={"filterby": filterby},
            total=Task.search_count(domain), page=page, step=self._items_per_page)
        jobs = Task.search(domain, order=order, limit=self._items_per_page,
                           offset=pager["offset"])
        values = self._prepare_portal_layout_values()
        values.update({
            # Fields such as the asset or the technician are on models the
            # portal user cannot read; the visits themselves were searched
            # with the user's own rights above.
            "jobs": jobs.sudo(),
            "page_name": "fm_jobs",
            "pager": pager,
            "default_url": "/my/jobs",
            "searchbar_filters": filters,
            "filterby": filterby,
            "job_service": self._fm_job_service,
        })
        return request.render("fm_portal.portal_my_fm_jobs", values)

    # ------------------------------------------------------------------
    # Certificates & service reports
    # ------------------------------------------------------------------
    def _fm_certificates(self):
        """The compliance certificates of the assets the customer's
        contracts cover, or raised from one of their visits.

        A certificate carries no customer of its own -- it belongs to an
        asset -- so ownership is read through the contract, which is where
        an asset becomes a customer's.
        """
        customer = self._fm_customer()
        orders = request.env["sale.order"].sudo().search([
            ("partner_id", "child_of", customer.id),
            ("is_fm_contract", "=", True),
            ("state", "=", "sale"),
        ])
        return request.env["fm.compliance.certificate"].sudo().search([
            "|",
            ("asset_id", "in", orders.fm_asset_ids.ids),
            ("related_workorder_id.partner_id", "child_of", customer.id),
        ], order="expiry_date desc, id desc")

    def _fm_service_reports(self):
        return request.env["project.task"].search(
            self._fm_jobs_domain("done"), order="planned_date_begin desc, id desc").sudo()

    @http.route("/my/jobs/<int:task_id>/report", type="http", auth="user", website=True)
    def portal_fm_job_report(self, task_id, **kw):
        """The service report of a completed visit.

        Odoo's own field service report refuses to render for a visit with
        no timesheet, product or worksheet -- which is most of them here --
        so such a visit gets the FM Service Work Order instead of an error.
        """
        task = request.env["project.task"].search(
            Domain.AND([self._fm_jobs_domain("done"), [("id", "=", task_id)]])).sudo()
        if not task:
            return request.redirect("/my/jobs?filterby=done")
        report_ref = ("industry_fsm.task_custom_report" if task._is_fsm_report_available()
                      else "fm_documents.action_report_fm_workorder")
        return self._show_report(model=task, report_type="pdf", report_ref=report_ref, download=True)

    @http.route("/my/fm-documents", type="http", auth="user", website=True)
    def portal_my_fm_documents(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update({
            "certificates": self._fm_certificates(),
            "reports": self._fm_service_reports(),
            "page_name": "fm_documents",
            "job_service": self._fm_job_service,
        })
        return request.render("fm_portal.portal_my_fm_documents", values)

    @http.route("/my/fm-documents/certificate/<int:certificate_id>", type="http", auth="user", website=True)
    def portal_fm_certificate_download(self, certificate_id, **kw):
        """The certificate as issued when one is on file, else ours."""
        certificate = self._fm_certificates().filtered(lambda c: c.id == certificate_id)
        if not certificate:
            return request.redirect("/my/fm-documents")
        if certificate.document_attachment_id:
            return request.env["ir.binary"]._get_stream_from(
                certificate.document_attachment_id).get_response(as_attachment=True)
        return self._show_report(
            model=certificate, report_type="pdf",
            report_ref="fm_documents.action_report_fm_certificate", download=True)

    # ------------------------------------------------------------------
    # Service requests
    # ------------------------------------------------------------------
    def _fm_my_requests(self):
        return request.env["crm.lead"].sudo().search(
            [("partner_id", "child_of", self._fm_customer().id)],
            order="create_date desc", limit=10)

    @http.route("/my/service-request", type="http", auth="user", website=True,
                methods=["GET", "POST"])
    def portal_fm_service_request(self, **post):
        partner = request.env.user.partner_id
        error = {}
        if request.httprequest.method == "POST":
            service = post.get("service")
            description = (post.get("description") or "").strip()
            if service not in dict(SERVICE_LINES):
                error["service"] = _("Choose the service you need.")
            if not description:
                error["description"] = _("Tell us what needs doing.")
            if not error:
                lead = self._fm_create_service_request(partner, service, post)
                return request.redirect("/my/service-request?submitted=%s" % lead.id)
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "fm_service_request",
            "services": SERVICE_LINES,
            "service_labels": dict(SERVICE_LINES),
            "partner": partner,
            "post": post if error else {},
            "error": error,
            "submitted": bool(post.get("submitted")) and not error,
            "submitted_request": self._fm_submitted_request(post.get("submitted")) if not error else False,
            "my_requests": self._fm_my_requests(),
        })
        return request.render("fm_portal.portal_fm_service_request", values)

    def _fm_submitted_request(self, ref):
        """The lead just submitted, for the confirmation popup -- only when
        it really is this customer's own request (the id is in the URL)."""
        if not ref or not str(ref).isdigit():
            return False
        lead = request.env["crm.lead"].sudo().browse(int(ref)).exists()
        customer = request.env.user.partner_id.commercial_partner_id
        if not lead or lead.partner_id.commercial_partner_id != customer:
            return False
        return lead

    def _fm_create_service_request(self, partner, service, post):
        """A lead against the customer, as a website booking makes one --
        so it enters the same Sales → Accounts → Operations handover rather
        than a queue of its own nobody watches."""
        label = dict(SERVICE_LINES)[service]
        customer = partner.commercial_partner_id
        lines = [
            (_("Service"), label),
            (_("Site"), (post.get("site") or "").strip()),
            (_("Preferred date"), (post.get("preferred_date") or "").strip()),
            (_("Requested by"), partner.name),
        ]
        description = Markup("").join(
            Markup("<p><b>%s:</b> %s</p>") % (name, value) for name, value in lines if value
        ) + Markup("<p>%s</p>") % escape(post.get("description").strip())
        vals = {
            "name": _("%(service)s — %(customer)s", service=label, customer=customer.name),
            "partner_id": partner.id,
            "contact_name": partner.name,
            "email_from": partner.email,
            "phone": partner.phone,
            "description": description,
        }
        website = request.website
        if "crm_default_team_id" in website._fields and website.crm_default_team_id:
            vals["team_id"] = website.crm_default_team_id.id
        if "crm_default_user_id" in website._fields and website.crm_default_user_id:
            vals["user_id"] = website.crm_default_user_id.id
        lead = request.env["crm.lead"].sudo().create(vals)
        lead.message_post(body=_("Service request submitted from the customer portal by %s.", partner.name))
        return lead
