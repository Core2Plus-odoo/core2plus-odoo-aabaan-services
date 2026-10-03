# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.addons.aabaan_letterhead import tools as letterhead
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    aabaan_audit_trail_html = fields.Html(
        string="Document Audit Trail", compute='_compute_aabaan_audit_trail_html',
        sanitize=False,
        help="Every row is a real system event — created/posted timestamps, "
             "whether it was actually emailed, real payments reconciled "
             "against it, credit notes issued against it. A milestone that "
             "hasn't happened yet simply doesn't appear; nothing here is "
             "estimated.")

    # ------------------------------------------------------------------
    # print helpers
    # ------------------------------------------------------------------

    def aabaan_tax_invoice_guard(self):
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_(
                "The Aaban Tax Invoice layout is for customer invoices and "
                "credit notes only — this document is a %s.")
                % (dict(self._fields['move_type'].selection).get(
                    self.move_type, self.move_type)))

    def _aabaan_document_title(self):
        self.ensure_one()
        return 'Tax Credit Note' if self.move_type == 'out_refund' else 'Tax Invoice'

    def _aabaan_line_desc(self, line):
        return letterhead.line_desc(line)

    def _aabaan_numbered_lines(self):
        self.ensure_one()
        rows, counter = [], 0
        for line in self.invoice_line_ids:
            if line.display_type:
                rows.append({'no': None, 'line': line})
            else:
                counter += 1
                rows.append({'no': counter, 'line': line})
        return rows

    def _aabaan_amount_in_words(self):
        self.ensure_one()
        return letterhead.amount_in_words(self)

    def _aabaan_reverse_charge(self):
        self.ensure_one()
        fp = self.fiscal_position_id
        return bool(fp and 'reverse' in (fp.name or '').casefold())

    def _aabaan_tax_lines(self):
        """Per-tax breakdown (name, rate, base, amount) built from the
        move's own lines — amounts taken as absolute values so the result
        doesn't depend on debit/credit sign convention, which differs
        between invoices and credit notes."""
        self.ensure_one()
        groups, order = {}, []
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            for tax in line.tax_ids:
                if tax.id not in groups:
                    groups[tax.id] = {
                        'name': tax.name, 'rate': tax.amount,
                        'base': 0.0, 'amount': 0.0}
                    order.append(tax.id)
                groups[tax.id]['base'] += line.price_subtotal
        for line in self.line_ids.filtered(lambda l: l.tax_line_id):
            if line.tax_line_id.id in groups:
                groups[line.tax_line_id.id]['amount'] += abs(line.balance)
        return [groups[key] for key in order]

    # ------------------------------------------------------------------
    # Document Audit Trail — every row is a real, queryable system event;
    # nothing here is estimated or reconstructed.
    # ------------------------------------------------------------------

    def _aabaan_audit_trail(self):
        self.ensure_one()
        trail = [{
            'label': 'Created',
            'date': self.create_date,
            'amount': None,
            'detail': self.create_uid.name or '',
        }]

        if self.state == 'posted':
            posted_on = self.date or self.invoice_date
            trail.append({
                'label': 'Posted',
                'date': (fields.Datetime.to_datetime(posted_on)
                         if posted_on else self.write_date),
                'amount': None,
                'detail': ('Journal entry date %s' % posted_on.strftime('%d-%b-%Y')
                           if posted_on else ''),
            })

        mail = self.env['mail.mail'].sudo().search([
            ('model', '=', 'account.move'), ('res_id', '=', self.id),
            ('state', '=', 'sent')], order='create_date asc', limit=1)
        if mail:
            trail.append({
                'label': 'Sent to customer',
                'date': mail.create_date,
                'amount': None,
                'detail': mail.email_to or self.partner_id.email or '',
            })

        receivable = self.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable')
        partials = receivable.matched_credit_ids | receivable.matched_debit_ids
        seen_payments = self.env['account.payment']
        for partial in partials.sorted('max_date'):
            other_lines = (partial.debit_move_id + partial.credit_move_id).filtered(
                lambda l: l not in receivable)
            payment = other_lines.payment_id[:1]
            if not payment or payment in seen_payments:
                continue
            seen_payments |= payment
            trail.append({
                'label': 'Payment received',
                'date': (fields.Datetime.to_datetime(payment.date)
                         if payment.date
                         else fields.Datetime.to_datetime(partial.max_date)),
                'amount': partial.amount,
                'detail': payment.journal_id.name or '',
            })

        if 'reversal_move_ids' in self._fields:
            for rev in self.reversal_move_ids.filtered(lambda m: m.state == 'posted'):
                trail.append({
                    'label': 'Credit note issued',
                    'date': (fields.Datetime.to_datetime(rev.invoice_date)
                             if rev.invoice_date else rev.create_date),
                    'amount': -rev.amount_total,
                    'detail': rev.name,
                })
        if 'reversed_entry_id' in self._fields and self.reversed_entry_id:
            trail.append({
                'label': 'Credits',
                'date': (fields.Datetime.to_datetime(self.invoice_date)
                         if self.invoice_date else self.create_date),
                'amount': None,
                'detail': 'Tax Invoice %s' % self.reversed_entry_id.name,
            })

        trail.sort(key=lambda row: row['date'] or self.create_date)
        return trail

    @api.depends('state', 'invoice_date')
    def _compute_aabaan_audit_trail_html(self):
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                move.aabaan_audit_trail_html = False
                continue
            if move.state == 'draft':
                move.aabaan_audit_trail_html = Markup(
                    '<p class="text-muted">Nothing to show yet — the audit '
                    'trail starts once this document is posted.</p>')
                continue
            rows = move._aabaan_audit_trail()
            parts = [
                '<table class="table table-sm"><thead><tr>'
                '<th>Event</th><th>Date</th><th>Amount</th><th>Detail</th>'
                '</tr></thead><tbody>']
            for row in rows:
                date_s = (row['date'].strftime('%d-%b-%Y %H:%M')
                          if row['date'] else '')
                if row['amount'] is not None:
                    amount_s = '%.2f %s' % (
                        row['amount'],
                        move.currency_id.symbol or move.currency_id.name)
                else:
                    amount_s = ''
                parts.append(
                    '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                        escape(row['label']), escape(date_s),
                        escape(amount_s), escape(row['detail'] or '')))
            parts.append('</tbody></table>')
            move.aabaan_audit_trail_html = Markup(''.join(parts))
