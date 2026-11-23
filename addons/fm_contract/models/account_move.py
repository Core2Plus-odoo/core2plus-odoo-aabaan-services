# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_fm_create_sale_orders(self):
        """Server action on the invoice list: give each selected customer
        invoice a confirmed sale order built from its lines.

        The order's lines are linked to the invoice's lines (sale_line_ids),
        which is the link Odoo itself keeps between an order and its invoice:
        the invoice then shows the native "Sale Orders" smart button, and the
        order counts the invoice as already invoiced. Nothing new is billed.

        Confirming makes no job and no contract: the work behind an invoice
        that already exists is not new work to schedule.

        Skipped, and listed at the end: anything that is not a customer
        invoice, a cancelled invoice, one already linked to a sale order, and
        one whose order could not be confirmed (the reason is given).
        """
        SaleOrder = self.env["sale.order"]
        created = SaleOrder
        skipped = []
        for move in self:
            reason = move._fm_sale_order_skip_reason()
            if reason:
                skipped.append((move.display_name, reason))
                continue
            try:
                with self.env.cr.savepoint():
                    created |= move._fm_create_confirmed_sale_order()
            except UserError as error:
                skipped.append((move.display_name, str(error).splitlines()[0]))

        message = _("%s sale order(s) created and confirmed.", len(created))
        if skipped:
            message += "\n" + _("Skipped:") + "\n" + "\n".join(
                "• %s — %s" % item for item in skipped)
        next_action = {"type": "ir.actions.act_window_close"}
        if created:
            next_action = {
                "type": "ir.actions.act_window",
                "name": _("Sale Orders from Invoices"),
                "res_model": "sale.order",
                "view_mode": "list,form",
                "views": [(False, "list"), (False, "form")],
                "domain": [("id", "in", created.ids)],
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Create Sale Orders"),
                "message": message,
                "type": "warning" if skipped else "success",
                "sticky": bool(skipped),
                "next": next_action,
            },
        }

    def _fm_sale_order_skip_reason(self):
        self.ensure_one()
        if self.move_type != "out_invoice":
            return _("not a customer invoice")
        if self.state == "cancel":
            return _("cancelled")
        if self.line_ids.sale_line_ids:
            return _("already linked to %s", ", ".join(
                self.line_ids.sale_line_ids.order_id.mapped("name")))
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        if not lines:
            return _("no invoice lines")
        if lines.filtered(lambda l: not l.product_id):
            return _("a line has no product")
        if self.currency_id != self.company_id.currency_id and not self._fm_pricelist():
            return _("no pricelist in %s", self.currency_id.name)
        return False

    def _fm_pricelist(self):
        """A pricelist in the invoice's currency, so the order's amounts
        are in the same currency as the invoice."""
        return self.env["product.pricelist"].search([
            ("currency_id", "=", self.currency_id.id),
            ("company_id", "in", (False, self.company_id.id)),
        ], limit=1)

    def _fm_create_confirmed_sale_order(self):
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type in ("product", "line_section", "line_note"))
        order_vals = {
            "partner_id": self.partner_id.id,
            "partner_invoice_id": self.partner_id.id,
            "partner_shipping_id": (self.partner_shipping_id or self.partner_id).id,
            "company_id": self.company_id.id,
            "client_order_ref": self.ref or False,
            "origin": self.name,
            "fiscal_position_id": self.fiscal_position_id.id,
            "payment_term_id": self.invoice_payment_term_id.id,
            "user_id": self.invoice_user_id.id,
            "team_id": self.team_id.id,
            "order_line": [],
        }
        pricelist = self._fm_pricelist()
        if pricelist:
            order_vals["pricelist_id"] = pricelist.id
        invoice_lines = []
        for line in lines.sorted("sequence"):
            if line.display_type != "product":
                order_vals["order_line"].append((0, 0, {
                    "display_type": line.display_type, "name": line.name,
                    "sequence": line.sequence}))
                continue
            invoice_lines.append(line)
            order_vals["order_line"].append((0, 0, {
                "sequence": line.sequence,
                "product_id": line.product_id.id,
                "name": line.name,
                "product_uom_qty": line.quantity,
                "product_uom_id": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "tax_ids": [(6, 0, line.tax_ids.ids)],
                "analytic_distribution": line.analytic_distribution,
            }))
        order = self.env["sale.order"].create(order_vals)
        order.with_context(
            disable_project_task_generation=True,
            fm_skip_auto_schedule=True,
            fm_skip_contract_detect=True,
        ).action_confirm()
        # Confirming stamps the order with today; it was agreed when it
        # was invoiced.
        if self.invoice_date:
            order.date_order = self.invoice_date
        product_lines = order.order_line.filtered(lambda l: not l.display_type).sorted("sequence")
        for invoice_line, order_line in zip(invoice_lines, product_lines):
            invoice_line.sale_line_ids = [(6, 0, order_line.ids)]
        order.message_post(body=Markup(_("Created from invoice %s.")) % self._get_html_link())
        self.message_post(body=Markup(_("Sale order %s created from this invoice.")) % order._get_html_link())
        return order
