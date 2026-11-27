# -*- coding: utf-8 -*-
"""The FM Tax Invoice, and the audit trail behind it.

Ported from ``aabaan_invoice_report`` on the retired build (consolidation
plan, P3). Two things came across and one deliberately did not:

* The **print helpers** are methods here rather than module-level functions
  in a shared "letterhead" module. QWeb calls them on the record, and this
  build already has one letterhead -- Odoo's own ``web.external_layout``,
  which every other fm_documents report uses. A second hardcoded letterhead
  is exactly the duplication this port exists to remove.
* The **audit trail** is built only from events the system can actually
  prove: create and post timestamps, a ``mail.mail`` that really was sent,
  payments really reconciled against the receivable, and credit notes
  really issued. A milestone that has not happened does not appear. Nothing
  is estimated -- an invented date on a document a customer may dispute is
  worse than a gap.

Every field this touches outside ``account`` itself is resolved at runtime
(``in self._fields``). ``branch_id`` in particular belongs to ``fm_branch``,
which depends on *this* module -- so it can be present or absent and the
document has to print either way.
"""
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

CUSTOMER_MOVES = ("out_invoice", "out_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    fm_audit_trail_html = fields.Html(
        string="Document Audit Trail",
        compute="_compute_fm_audit_trail_html",
        sanitize=False,
        help="Every row is a real system event — when the invoice was created "
             "and posted, whether it was actually emailed, payments genuinely "
             "reconciled against it, and any credit notes issued. A milestone "
             "that has not happened yet simply does not appear; nothing here "
             "is estimated.",
    )

    # ------------------------------------------------------------------
    # print helpers — called from the QWeb template on the record
    # ------------------------------------------------------------------

    def _fm_tax_invoice_guard(self):
        """Refuse to print the layout for anything but a customer document.

        The Print menu binding is on ``account.move`` as a whole because
        Odoo has no way to bind a report to a subset of a model's records.
        So the guard is what stops a vendor bill coming out headed "Tax
        Invoice" — a document that would be wrong in a way the reader
        cannot see.
        """
        self.ensure_one()
        if self.move_type not in CUSTOMER_MOVES:
            # fields_get rather than the field's own selection attribute:
            # it is the documented, translated read and does not depend on
            # whether the selection is a literal, a callable or a string.
            selection = self.fields_get(["move_type"])["move_type"]["selection"]
            label = dict(selection)
            raise UserError(_(
                "The FM Tax Invoice layout is for customer invoices and credit "
                "notes only — this document is a %s. Print it with Odoo's own "
                "Invoices entry instead.",
                label.get(self.move_type, self.move_type)))

    def _fm_invoice_branch(self):
        """The branch this invoice is issued from, or an empty record.

        fm_branch owns ``branch_id`` and depends on this module, so the
        branch is resolved at runtime; the command centre's derived branch
        is the fallback when the invoice itself carries none."""
        self.ensure_one()
        for fname in ("branch_id", "fm_cc_branch_id"):
            if fname in self._fields and self[fname]:
                return self[fname]
        return False

    def _fm_invoice_issuer(self):
        """Name and address printed as the issuer of the Tax Invoice:
        the branch's own trading name and address when the invoice has a
        branch that carries them, the company's otherwise."""
        self.ensure_one()
        company = self.company_id.sudo()
        branch = self._fm_invoice_branch()
        name = (branch and "invoice_name" in branch._fields and branch.invoice_name) or company.name
        if branch and branch.street:
            lines = [part for part in (branch.street, branch.city) if part]
            lines.append(company.country_id.name or "United Arab Emirates")
        else:
            partner = company.partner_id
            lines = [part for part in (partner.street, partner.street2,
                                       " ".join(p for p in (partner.city, partner.state_id.name) if p),
                                       partner.country_id.name) if part]
        return {
            "name": name,
            "lines": lines,
            "phone": (branch and branch.phone) or company.phone or "",
            "email": (branch and branch.email) or company.email or "",
        }

    @staticmethod
    def _fm_date(value):
        """Dates on the Tax Invoice read 27-Nov-2026, as the client asked."""
        return value.strftime("%d-%b-%Y") if value else ""

    def _fm_document_title(self):
        self.ensure_one()
        return _("Tax Credit Note") if self.move_type == "out_refund" else _("Tax Invoice")

    def _fm_document_title_ar(self):
        """The Arabic title. Both are the terms the FTA itself uses."""
        self.ensure_one()
        return "إشعار دائن ضريبي" if self.move_type == "out_refund" else "فاتورة ضريبية"

    def _fm_line_description(self, line):
        """The line name without its internal product code prefix.

        '[AAB-CLN-DEEP-2BR] Deep Cleaning — 2BR' prints as the name only:
        the code is ours, and a customer reading their invoice has no use
        for it.
        """
        name = (line.name or "").strip()
        code = line.product_id.default_code
        if code and name.startswith("[%s]" % code):
            name = name[len(code) + 2:].lstrip()
        return name

    def _fm_numbered_lines(self):
        """Invoice lines with a running number, sections and notes unnumbered.

        The number is wanted on the printed document (customers query "line
        4"), and it cannot be the loop index because sections and notes sit
        in the same recordset without being chargeable lines.
        """
        self.ensure_one()
        rows, counter = [], 0
        for line in self.invoice_line_ids:
            # Odoo 17+ marks a chargeable line display_type 'product', so a
            # plain truth test left every line unnumbered and the template
            # dropped the # cell, shifting the whole row one column left.
            if line.display_type in ("line_section", "line_note"):
                rows.append({"no": None, "line": line})
            else:
                counter += 1
                rows.append({"no": counter, "line": line})
        return rows

    def _fm_paid_stamp_date(self):
        """Date for the PAID stamp, or False when no stamp should print.

        Only a customer invoice that is actually settled (paid, or paid and
        waiting on the bank) gets a stamp, dated with its latest payment.
        A draft, an open or a partly paid invoice prints without one: a
        PAID stamp on money not received is a false receipt."""
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_receipt") \
                or self.state != "posted" \
                or self.payment_state not in ("paid", "in_payment"):
            return False
        # Two places a payment shows up: the reconciled-payments widget, and
        # (Odoo 18+) matched_payment_ids, which is the only link while a
        # payment is still "in process" with the bank and the widget is empty.
        widget = self.sudo().invoice_payments_widget or {}
        dates = [p["date"] for p in widget.get("content", [])
                 if p.get("date") and not p.get("is_exchange")]
        if "matched_payment_ids" in self._fields:
            dates += [p.date for p in self.sudo().matched_payment_ids
                      if p.date and p.state in ("in_process", "paid")]
        return max(dates) if dates else self.invoice_date

    def _fm_amount_in_words(self):
        """The grand total spelled out, or '' when the currency cannot.

        A report must never fail over a wording nicety, so this swallows
        the error rather than letting an unsupported currency take the
        whole document down.
        """
        self.ensure_one()
        try:
            return self.currency_id.amount_to_text(self.amount_total)
        except Exception:  # noqa: BLE001 - see docstring
            return ""

    def _fm_reverse_charge(self):
        """True only when this invoice's own fiscal position says so.

        Never asserted by default: telling a customer VAT is theirs to
        account for when it is not is a tax error on a document they will
        file.
        """
        self.ensure_one()
        position = self.fiscal_position_id
        return bool(position and "reverse" in (position.name or "").casefold())

    def _fm_tax_breakdown(self):
        """Per-tax rows (name, rate, base, amount) built from the move's lines.

        Tax amounts are taken as absolute values so the result does not
        depend on the debit/credit sign convention, which is inverted
        between an invoice and a credit note.
        """
        self.ensure_one()
        groups, order = {}, []
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            for tax in line.tax_ids:
                if tax.id not in groups:
                    groups[tax.id] = {
                        "name": tax.name, "rate": tax.amount,
                        "base": 0.0, "amount": 0.0,
                    }
                    order.append(tax.id)
                groups[tax.id]["base"] += line.price_subtotal
        for line in self.line_ids.filtered(lambda l: l.tax_line_id):
            if line.tax_line_id.id in groups:
                groups[line.tax_line_id.id]["amount"] += abs(line.balance)
        return [groups[key] for key in order]

    def _fm_source_contract(self):
        """The FM contract behind this invoice, if there is one.

        Walks the same link ``fm_branch`` uses, and answers empty rather
        than guessing when the sale bridge is not installed.
        """
        self.ensure_one()
        if self.move_type not in CUSTOMER_MOVES:
            return self.env["sale.order"]
        if "sale_line_ids" not in self.env["account.move.line"]._fields:
            return self.env["sale.order"]
        orders = self.invoice_line_ids.sale_line_ids.order_id
        if "is_fm_contract" in orders._fields:
            orders = orders.filtered("is_fm_contract")
        return orders[:1]

    # ------------------------------------------------------------------
    # Document Audit Trail
    # ------------------------------------------------------------------

    def _fm_audit_trail(self):
        """Real, queryable events only — see the module docstring."""
        self.ensure_one()
        trail = [{
            "label": _("Created"),
            "date": self.create_date,
            "amount": None,
            "detail": self.create_uid.name or "",
        }]

        if self.state == "posted":
            posted_on = self.date or self.invoice_date
            trail.append({
                "label": _("Posted"),
                "date": (fields.Datetime.to_datetime(posted_on)
                         if posted_on else self.write_date),
                "amount": None,
                "detail": (_("Journal entry date %s", posted_on.strftime("%d-%b-%Y"))
                           if posted_on else ""),
            })

        mail = self.env["mail.mail"].sudo().search(
            [("model", "=", "account.move"), ("res_id", "=", self.id),
             ("state", "=", "sent")],
            order="create_date asc", limit=1)
        if mail:
            trail.append({
                "label": _("Sent to customer"),
                "date": mail.create_date,
                "amount": None,
                "detail": mail.email_to or self.partner_id.email or "",
            })

        trail.extend(self._fm_audit_trail_payments())

        if "reversal_move_ids" in self._fields:
            for reversal in self.reversal_move_ids.filtered(lambda m: m.state == "posted"):
                trail.append({
                    "label": _("Credit note issued"),
                    "date": (fields.Datetime.to_datetime(reversal.invoice_date)
                             if reversal.invoice_date else reversal.create_date),
                    "amount": -reversal.amount_total,
                    "detail": reversal.name or "",
                })
        if "reversed_entry_id" in self._fields and self.reversed_entry_id:
            trail.append({
                "label": _("Credits"),
                "date": (fields.Datetime.to_datetime(self.invoice_date)
                         if self.invoice_date else self.create_date),
                "amount": None,
                "detail": _("Tax Invoice %s", self.reversed_entry_id.name or ""),
            })

        trail.sort(key=lambda row: row["date"] or self.create_date)
        return trail

    def _fm_audit_trail_payments(self):
        """Payments actually reconciled against the receivable line.

        Not ``amount_residual`` arithmetic: a residual tells you money
        arrived, not when or through which journal. The partial
        reconciliations do, and they are what an auditor would look at.

        ``payment_id`` on the move line is checked rather than assumed —
        this compute renders on every customer invoice form, so a missing
        field has to cost a row, not the page.
        """
        self.ensure_one()
        rows = []
        if "payment_id" not in self.env["account.move.line"]._fields:
            return rows
        receivable = self.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable")
        partials = receivable.matched_credit_ids | receivable.matched_debit_ids
        seen = self.env["account.payment"]
        for partial in partials.sorted("max_date"):
            counterpart = (partial.debit_move_id + partial.credit_move_id).filtered(
                lambda l: l not in receivable)
            payment = counterpart.payment_id[:1]
            if not payment or payment in seen:
                continue
            seen |= payment
            rows.append({
                "label": _("Payment received"),
                "date": (fields.Datetime.to_datetime(payment.date) if payment.date
                         else fields.Datetime.to_datetime(partial.max_date)),
                "amount": partial.amount,
                "detail": payment.journal_id.name or "",
            })
        return rows

    @api.depends("state", "invoice_date", "payment_state")
    def _compute_fm_audit_trail_html(self):
        for move in self:
            if move.move_type not in CUSTOMER_MOVES:
                move.fm_audit_trail_html = False
                continue
            if move.state == "draft":
                move.fm_audit_trail_html = Markup(
                    '<p class="text-muted">%s</p>') % _(
                    "Nothing to show yet — the audit trail starts once this "
                    "document is posted.")
                continue
            parts = [Markup(
                '<table class="table table-sm"><thead><tr>'
                '<th>%s</th><th>%s</th><th>%s</th><th>%s</th>'
                '</tr></thead><tbody>') % (
                    _("Event"), _("Date"), _("Amount"), _("Detail"))]
            for row in move._fm_audit_trail():
                date_text = row["date"].strftime("%d-%b-%Y %H:%M") if row["date"] else ""
                if row["amount"] is None:
                    amount_text = ""
                else:
                    amount_text = "%.2f %s" % (
                        row["amount"],
                        move.currency_id.symbol or move.currency_id.name or "")
                parts.append(Markup(
                    "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>") % (
                        escape(row["label"]), escape(date_text),
                        escape(amount_text), escape(row["detail"] or "")))
            parts.append(Markup("</tbody></table>"))
            move.fm_audit_trail_html = Markup("").join(parts)
