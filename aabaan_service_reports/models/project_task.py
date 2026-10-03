# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

KIND_HINTS = {
    'tank': ('tank',),
    'termite': ('termite', 'anti-termite', 'antitermite'),
}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def aabaan_doc_vals(self):
        """Everything the service documents print, resolved with the same
        runtime guards as the rest of the build: manual x_* fields may be
        absent and every value degrades to empty."""
        self.ensure_one()
        order = self.sale_order_id

        def selection_label(record, fname):
            if not record or fname not in record._fields:
                return ''
            value = record[fname]
            if not value:
                return ''
            info = record.fields_get([fname], ['selection']).get(fname) or {}
            return dict(info.get('selection') or {}).get(value, value)

        def local(dt):
            if not dt:
                return ''
            return fields.Datetime.context_timestamp(self, dt)\
                .strftime('%d-%b-%Y %H:%M')

        completed = self.visit_completed_at
        return {
            'visit_type': selection_label(self, 'x_visit_type'),
            'emirate': selection_label(order, 'x_emirate_regime'),
            'service_line': selection_label(order, 'x_service_line'),
            'order_ref': order.name if order else '',
            'technician': self.user_ids[:1].name or '',
            'planned': local(self['planned_date_begin']
                             if 'planned_date_begin' in self._fields else False),
            'checkin': local(self.visit_started_at),
            'checkout': local(completed),
            'completed_date': (
                fields.Datetime.context_timestamp(self, completed)
                .strftime('%d-%b-%Y') if completed else ''),
            'warranty_until': (
                (fields.Datetime.context_timestamp(self, completed)
                 + relativedelta(years=10)).strftime('%d-%b-%Y')
                if completed else ''),
            'duration': self.visit_duration_actual,
        }

    def aabaan_service_kind(self):
        """Best-effort service kind from the contract's service line, the
        order lines and the visit name — used only to guard certificates."""
        self.ensure_one()
        order = self.sale_order_id
        haystack = [self.name or '']
        if order:
            if 'x_service_line' in order._fields and order['x_service_line']:
                haystack.append(str(order['x_service_line']))
            haystack.extend(
                line.name or '' for line in order.order_line
                if not line.display_type)
        text = ' '.join(haystack).casefold()
        for kind, hints in KIND_HINTS.items():
            if any(hint in text for hint in hints):
                return kind
        return ''

    def aabaan_certificate_guard(self, kind):
        """Fool-proof: the wrong certificate on the wrong job is blocked
        with a reason, not printed."""
        label = {'tank': _("Water-Tank Cleaning Certificate"),
                 'termite': _("Anti-Termite Warranty Certificate")}[kind]
        for task in self:
            if not task.visit_completed_at:
                raise UserError(_(
                    "%(doc)s: complete the visit \"%(task)s\" first — a "
                    "certificate can only be issued for completed work.",
                    doc=label, task=task.display_name))
            if task.aabaan_service_kind() != kind:
                raise UserError(_(
                    "%(doc)s: \"%(task)s\" does not look like a %(kind)s job "
                    "(checked the contract's service line, its lines and the "
                    "visit name). Print the matching document, or set the "
                    "service line on the contract.",
                    doc=label, task=task.display_name, kind=kind))
        return True
