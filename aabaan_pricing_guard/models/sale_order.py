# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    aabaan_free_ok = fields.Boolean(
        string="Intentionally Free",
        help="Tick only when this line is deliberately not charged — a free "
             "follow-up, a call-out covered by the contract entitlement, or "
             "an agreed goodwill gesture. Without this tick a zero-value "
             "line blocks confirmation, so an AED 0 product cannot slip into "
             "a quotation unnoticed.")
    aabaan_free_reason = fields.Char(
        string="Why Free",
        help="Recorded on the order for the audit trail — required when the "
             "line is marked intentionally free.")

    @api.onchange('aabaan_free_ok')
    def _onchange_aabaan_free_ok(self):
        if not self.aabaan_free_ok:
            self.aabaan_free_reason = False


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _aabaan_zero_value_lines(self):
        """Product lines that would bill nothing. Measured on the subtotal,
        not the unit price, so a 100% discount is caught as well as an
        AED 0 product — both underbill exactly the same way."""
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: (
                not line.display_type
                and line.product_uom_qty > 0
                and line.currency_id.is_zero(line.price_subtotal)
                and not line.aabaan_free_ok))

    def _aabaan_check_zero_value(self):
        """Confirmation gate. The catalogue carries legacy duplicate SKUs
        priced at AED 0 alongside the correctly priced ones; picking the
        wrong one silently bills nothing. This makes that impossible to do
        by accident while leaving the deliberate case one tick away."""
        for order in self:
            lines = order._aabaan_zero_value_lines()
            if not lines:
                continue
            listed = "\n".join(
                "  • %s" % (line.product_id.display_name or line.name or '?')
                for line in lines)
            raise UserError(_(
                "%(order)s cannot be confirmed — these lines would bill "
                "nothing:\n\n%(lines)s\n\n"
                "Either set the correct price (the catalogue holds legacy "
                "duplicate products priced at AED 0 — check you picked the "
                "priced one), or tick \"Intentionally Free\" on the line and "
                "give the reason, if the work really is not being charged.",
                order=order.display_name, lines=listed))

    def _aabaan_check_free_reason(self):
        for order in self:
            missing = order.order_line.filtered(
                lambda line: line.aabaan_free_ok and not (
                    line.aabaan_free_reason or '').strip())
            if missing:
                raise UserError(_(
                    "%(order)s: give a reason for every line marked "
                    "\"Intentionally Free\" — a line that bills nothing has "
                    "to be explainable later.\n\n%(lines)s",
                    order=order.display_name,
                    lines="\n".join(
                        "  • %s" % (line.product_id.display_name
                                    or line.name or '?')
                        for line in missing)))

    def action_confirm(self):
        self._aabaan_check_zero_value()
        self._aabaan_check_free_reason()
        return super().action_confirm()
