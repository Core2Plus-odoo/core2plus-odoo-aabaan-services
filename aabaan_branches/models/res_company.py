# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import timedelta

from odoo import _, api, fields, models

RENEWAL_HORIZON_DAYS = 60


class ResCompany(models.Model):
    _inherit = 'res.company'

    aabaan_licence_expiry = fields.Date(
        string="Trade Licence Expiry",
        help="From the licence document. A daily check raises a renewal "
             "activity 60 days before expiry (and keeps raising it while "
             "expired). Branch licences are tracked on the Emirate "
             "analytic dimension, not here.")

    def _aabaan_schedule_licence_renewal(self, summary, registry, expiry,
                                         today, horizon):
        """Raise a single open renewal activity on the company partner.

        An open activity blocks duplicates regardless of its deadline — an
        expired licence must not re-alert every day.
        """
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return
        existing = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
            ('summary', '=', summary),
        ], limit=1)
        if existing:
            return
        todo = self.env.ref('mail.mail_activity_data_todo',
                            raise_if_not_found=False)
        partner.activity_schedule(
            'mail.mail_activity_data_todo' if todo else False,
            date_deadline=max(today, min(expiry, horizon)),
            summary=summary,
            note=_("Licence %(reg)s expires on %(date)s. Renew it and "
                   "update the expiry date.",
                   reg=registry or '-', date=expiry),
        )

    @api.model
    def _cron_aabaan_licence_expiry(self):
        """Check the company licence and every branch licence.

        Branches are the Emirate analytic accounts, so their renewals are
        raised against the company partner too — distinguished by the
        branch name in the summary.
        """
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=RENEWAL_HORIZON_DAYS)

        for company in self.search([
                ('aabaan_licence_expiry', '!=', False),
                ('aabaan_licence_expiry', '<=', horizon)]):
            company._aabaan_schedule_licence_renewal(
                _("Trade licence renewal — %s", company.name),
                company.company_registry,
                company.aabaan_licence_expiry,
                today, horizon)

        main = self.env.ref('base.main_company', raise_if_not_found=False)
        if not main:
            return
        branches = self.env['account.analytic.account'].sudo().search([
            ('aabaan_licence_expiry', '!=', False),
            ('aabaan_licence_expiry', '<=', horizon)])
        for branch in branches:
            main._aabaan_schedule_licence_renewal(
                _("Trade licence renewal — %s branch", branch.name),
                branch.aabaan_licence_no,
                branch.aabaan_licence_expiry,
                today, horizon)
