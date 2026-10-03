# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _aabaan_voucher_memo(self):
        self.ensure_one()
        for fname in ('memo', 'ref'):
            if fname in self._fields:
                return self[fname] or ''
        return ''

    def _aabaan_amount_words(self):
        self.ensure_one()
        try:
            return self.currency_id.amount_to_text(self.amount)
        except Exception:
            return ''

    def _aabaan_voucher_lines(self):
        """Reconciled bills/invoices with their branch (Emirate-plan) tags,
        for the printed voucher."""
        self.ensure_one()
        Move = self.env['account.move']
        emirate_plan, _service = Move._aabaan_analytic_plans()
        moves = Move
        for fname in ('reconciled_bill_ids', 'reconciled_invoice_ids'):
            if fname in self._fields:
                moves |= self[fname]
        out = []
        for move in moves:
            names = set()
            if emirate_plan:
                for line in move.invoice_line_ids:
                    for key in (line.analytic_distribution or {}):
                        for part in str(key).split(','):
                            if part.strip().isdigit():
                                account = self.env['account.analytic.account']\
                                    .browse(int(part)).exists()
                                if account and account.root_plan_id.id == emirate_plan.id:
                                    names.add(account.name)
            out.append({'move': move, 'branches': ", ".join(sorted(names))})
        return out
