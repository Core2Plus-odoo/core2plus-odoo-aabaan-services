# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
import re

from odoo import _, api, models
from odoo.tools import html2plaintext

from odoo.addons.aabaan_visit_schedule.models.sale_order import _selection_key

# (label, word-boundary hints found in text, needle for the selection field)
EMIRATES = [
    ('Ajman', ('ajman',), 'ajman'),
    ('Sharjah', ('sharjah',), 'sharjah'),
    ('Dubai', ('dubai', 'deira',), 'dubai'),
    ('Umm Al Quwain', ('umm al quwain', 'umm al-quwain', 'uaq'), 'quwain'),
    ('Ras Al Khaimah', ('ras al khaimah', 'ras al-khaimah', 'rak'), 'khaimah'),
    ('Fujairah', ('fujairah',), 'fujairah'),
    ('Abu Dhabi', ('abu dhabi',), 'abu'),
]


def find_emirate(text):
    """First emirate whose hint appears as a whole word in the text."""
    haystack = (text or '').casefold()
    for label, hints, needle in EMIRATES:
        for hint in hints:
            if re.search(r'\b%s\b' % re.escape(hint), haystack):
                return label, hint, needle
    return None


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def aabaan_tag_emirates(self):
        """Skim every contract without an emirate and tag it from real
        evidence — service address, customer address, customer name, then
        the contract text. Human-set values are never overwritten; every
        tag posts its evidence in the chatter."""
        fname = 'x_emirate_regime'
        if fname not in self._fields:
            return {'missing_field': True, 'tagged': 0, 'no_evidence': 0,
                    'already': 0}
        orders = self.search([(fname, '=', False)])
        tagged = no_evidence = 0
        for order in orders:
            partner = order.partner_id
            ship = order.partner_shipping_id
            sources = []
            if ship and ship != partner:
                sources.append((_("service address"), ' '.join(filter(None, [
                    ship.city, ship.state_id.name, ship.street, ship.street2]))))
            sources.append((_("customer address"), ' '.join(filter(None, [
                partner.city, partner.state_id.name, partner.street,
                partner.street2]))))
            sources.append((_("customer name"), partner.name or ''))
            sources.append((_("contract text"), ' '.join(filter(None, [
                order.client_order_ref,
                html2plaintext(order.note) if order.note else '']))))

            hit = None
            for src_label, text in sources:
                found = find_emirate(text)
                if found:
                    hit = (src_label,) + found
                    break
            key = hit and _selection_key(order, fname, hit[3])
            if not key:
                no_evidence += 1
                continue
            order.write({fname: key})
            order.message_post(body=_(
                'Emirate tagged automatically: %(emirate)s — matched '
                '"%(hint)s" in the %(src)s.',
                emirate=hit[1], hint=hit[2], src=hit[0]))
            tagged += 1
        already = self.search_count([(fname, '!=', False)]) - tagged
        return {'missing_field': False, 'tagged': tagged,
                'no_evidence': no_evidence, 'already': already}

    def aabaan_emirate_label(self):
        """Human label of the contract's emirate selection value, or ''."""
        self.ensure_one()
        fname = 'x_emirate_regime'
        if fname not in self._fields or not self[fname]:
            return ''
        info = self.fields_get([fname], ['selection']).get(fname) or {}
        return dict(info.get('selection') or {}).get(self[fname], self[fname])
