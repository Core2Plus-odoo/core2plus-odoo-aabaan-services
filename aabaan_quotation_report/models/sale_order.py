# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
import re

from markupsafe import Markup

from odoo import models
from odoo.addons.aabaan_letterhead import tools as letterhead


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _aabaan_note_html(self):
        """The order's terms (articles), cleaned for print: the editor's
        fill-in placeholder chips (dashed border, pencil icon) become bold
        underlined text, so an unfilled placeholder reads as a blank to
        complete instead of an editing artefact."""
        self.ensure_one()
        html = str(self.note or '')
        if not html.strip():
            return ''
        html = html.replace('✎', '').replace('&#9998;', '')

        def clean_style(match):
            style = match.group(1)
            if 'dashed' in style:
                return ('style="font-weight: bold; padding: 0 3px; '
                        'border-bottom: 1px solid #1A1A1C;"')
            return match.group(0)

        html = re.sub(r'style="([^"]*)"', clean_style, html)
        return Markup(html)

    def _aabaan_line_desc(self, line):
        return letterhead.line_desc(line)

    def _aabaan_selection_display(self, fname):
        """Display label of a (possibly manual/Studio) field for report
        rendering. Returns '' when the field is missing or empty, so the
        report never depends on the database-defined x_* fields existing."""
        self.ensure_one()
        if fname not in self._fields:
            return ''
        value = self[fname]
        if not value:
            return ''
        field = self._fields[fname]
        if field.type == 'selection':
            selection = field.get_description(self.env).get('selection') or []
            return dict(selection).get(value, str(value))
        return str(value)

    def _aabaan_subject(self):
        """Subject line of the printed document, e.g.
        'PEST CONTROL AMC - VILLA 12, AL RASHIDIYA 2, AJMAN'."""
        self.ensure_one()
        parts = []
        # A contract can cover several services (e.g. pest control AND
        # water tank cleaning) — name all of them, dynamically.
        if hasattr(self, 'aabaan_service_names'):
            services = self.aabaan_service_names()
        else:
            single = self._aabaan_selection_display('x_service_line')
            services = [single] if single else []
        if services:
            parts.append(" + ".join(services))
        site = self._aabaan_selection_display('x_site_address')
        if site:
            parts.append(site)
        return " - ".join(part.upper() for part in parts)

    def _aabaan_numbered_lines(self):
        """Order lines with a running number for product rows; sections and
        notes keep no=None and render as full-width rows."""
        self.ensure_one()
        rows, counter = [], 0
        for line in self.order_line:
            if line.display_type:
                rows.append({'no': None, 'line': line})
            else:
                counter += 1
                rows.append({'no': counter, 'line': line})
        return rows

    def _aabaan_amount_in_words(self):
        self.ensure_one()
        return letterhead.amount_in_words(self)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _aabaan_uom_name(self):
        self.ensure_one()
        for fname in ('product_uom_id', 'product_uom'):
            if fname in self._fields and self[fname]:
                return self[fname].name
        return ''
