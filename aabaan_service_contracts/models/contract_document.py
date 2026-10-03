# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import timedelta

from odoo import _, api, fields, models


class AabaanContractDocument(models.Model):
    """The compliance document pack from the approved UI reference —
    Master Agreement, Insurance Certificate, ISO certification, MSDS pack,
    Staff Roster, etc. — with per-document validity tracking."""
    _name = 'aabaan.contract.document'
    _description = "Contract Compliance Document"
    _order = 'document_type, name'

    order_id = fields.Many2one(
        'sale.order', string="Contract", required=True, ondelete='cascade')
    name = fields.Char(required=True)
    document_type = fields.Selection([
        ('master_agreement', 'Master Agreement'),
        ('insurance', 'Insurance Certificate'),
        ('iso_cert', 'ISO / Quality Certificate'),
        ('msds', 'MSDS / Chemical Safety Pack'),
        ('staff_roster', 'Staff Roster'),
        ('other', 'Other'),
    ], default='other', required=True)
    datas = fields.Binary(string="File", attachment=True)
    file_name = fields.Char(string="Filename")
    valid_until = fields.Date(
        string="Valid Until",
        help="Leave blank for documents that don't expire (e.g. the "
             "signed Master Agreement itself).")
    document_status = fields.Selection([
        ('no_expiry', 'No Expiry'),
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], compute='_compute_document_status')

    @api.depends('valid_until')
    def _compute_document_status(self):
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=60)
        for doc in self:
            if not doc.valid_until:
                doc.document_status = 'no_expiry'
            elif doc.valid_until < today:
                doc.document_status = 'expired'
            elif doc.valid_until <= horizon:
                doc.document_status = 'expiring_soon'
            else:
                doc.document_status = 'valid'

    @api.model
    def _cron_aabaan_document_expiry(self):
        """Mirrors the licence-expiry cron in aabaan_branches: raise one
        renewal activity per expiring document, on the contract itself, no
        duplicates while it stays unresolved."""
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=60)
        todo = self.env.ref('mail.mail_activity_data_todo',
                            raise_if_not_found=False)
        for doc in self.search([
                ('valid_until', '!=', False),
                ('valid_until', '<=', horizon)]):
            order = doc.order_id
            summary = _("Contract document renewal — %s") % doc.name
            existing = self.env['mail.activity'].search([
                ('res_model', '=', 'sale.order'),
                ('res_id', '=', order.id),
                ('summary', '=', summary),
            ], limit=1)
            if existing:
                continue
            order.activity_schedule(
                'mail.mail_activity_data_todo' if todo else False,
                date_deadline=max(today, min(doc.valid_until, horizon)),
                summary=summary,
                note=_("%(doc)s (%(type)s) on %(order)s expires %(date)s. "
                       "Upload the renewed document and update its "
                       "Valid Until date.",
                       doc=doc.name, type=doc.document_type,
                       order=order.name, date=doc.valid_until),
            )
