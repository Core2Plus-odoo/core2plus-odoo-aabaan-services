# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import _, api, models

from .sale_order import find_emirate

# Confident name keywords only — a keyword that could mislead is left out.
# Candidates are matched against the NATIVE industry list (res.partner.industry)
# by name, first hit wins; nothing is ever created.
INDUSTRY_RULES = [
    (('cafeteria', 'restaurant', 'restuarant', 'catering', 'bakery',
      'cafe', 'coffee'), ['Food', 'Hospitality']),
    (('hypermarket', 'supermarket', 'grocery', 'minimart'),
     ['Retail', 'Wholesale']),
    (('school', 'nursery', 'institute', 'university', 'college'),
     ['Education']),
    (('hospital', 'clinic', 'pharmacy', 'medical'), ['Health', 'Hospital']),
    (('real estate', 'properties', 'property management'), ['Real Estate']),
    (('contracting', 'construction', 'builders'), ['Construction']),
    (('hotel', 'resort'), ['Hospitality', 'Accommodation', 'Entertainment']),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def aabaan_enrich_contacts(self):
        """Enrich customers with what the data already proves:

        - UAE state + country, from the contact's own address text or,
          failing that, from the emirate tagged on their contracts;
        - industry, from confident name keywords, mapped onto the native
          industry list (never invented, never created).

        Only empty fields are filled; every change posts its evidence."""
        Industry = self.env['res.partner.industry']
        country = self.env.ref('base.ae', raise_if_not_found=False)
        State = self.env['res.country.state']
        Sale = self.env['sale.order']

        industry_cache = {}

        def industry_for(name):
            text = (name or '').casefold()
            for keywords, candidates in INDUSTRY_RULES:
                keyword = next((k for k in keywords if k in text), None)
                if not keyword:
                    continue
                key = tuple(candidates)
                if key not in industry_cache:
                    match = Industry
                    for candidate in candidates:
                        match = Industry.search(
                            [('name', 'ilike', candidate)], limit=1)
                        if match:
                            break
                    industry_cache[key] = match
                if industry_cache[key]:
                    return industry_cache[key], keyword
            return None, None

        def state_for(emirate_label):
            if not (country and emirate_label):
                return State
            return State.search([
                ('country_id', '=', country.id),
                ('name', 'ilike', emirate_label.split()[0]),
            ], limit=1)

        partners = self.search([('customer_rank', '>', 0)])
        located = classified = 0
        for partner in partners:
            # --- emirate / state ---
            if not partner.state_id:
                own_text = ' '.join(filter(None, [
                    partner.city, partner.street, partner.street2,
                    partner.name]))
                found = find_emirate(own_text)
                src = _("the contact's own address and name")
                if not found and 'x_emirate_regime' in Sale._fields:
                    for order in Sale.search(
                            [('partner_id', '=', partner.id)], limit=10):
                        label = order.aabaan_emirate_label()
                        if label:
                            found = (label, label.casefold(), '')
                            src = _("the emirate tagged on contract %s") \
                                % order.name
                            break
                state = found and state_for(found[0])
                if state:
                    partner.write({'state_id': state.id,
                                   'country_id': country.id})
                    partner.message_post(body=_(
                        'Emirate set automatically: %(state)s — from %(src)s.',
                        state=state.name, src=src))
                    located += 1
            # --- industry ---
            if not partner.industry_id:
                industry, keyword = industry_for(partner.name)
                if industry:
                    partner.write({'industry_id': industry.id})
                    partner.message_post(body=_(
                        'Industry set automatically: %(industry)s — the name '
                        'contains "%(keyword)s". Correct it on this form if '
                        'the guess is wrong.',
                        industry=industry.name, keyword=keyword))
                    classified += 1
        return {'customers': len(partners), 'located': located,
                'classified': classified}
