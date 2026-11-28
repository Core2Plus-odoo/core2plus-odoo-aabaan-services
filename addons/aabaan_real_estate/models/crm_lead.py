# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .re_project import EMIRATES
from .re_unit import UNIT_TYPES

PORTALS = [
    ('bayut', 'Bayut'), ('propertyfinder', 'Property Finder'), ('dubizzle', 'Dubizzle'),
    ('meta', 'Meta (Facebook / Instagram)'), ('google', 'Google Ads'),
    ('website', 'Website'), ('whatsapp', 'WhatsApp'), ('walkin', 'Walk-in'),
    ('referral', 'Referral'), ('other', 'Other'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    re_is_real_estate = fields.Boolean(related='team_id.re_is_real_estate')
    re_portal = fields.Selection(PORTALS, string='Lead source', tracking=True)
    re_temperature = fields.Selection(
        [('hot', '🔥 Hot'), ('warm', '🌤 Warm'), ('cold', '❄ Cold')],
        string='Temperature', tracking=True)
    re_purpose = fields.Selection(
        [('buy', 'Buy'), ('invest', 'Invest'), ('rent', 'Rent')], string='Looking to')
    re_budget_min = fields.Monetary('Budget from', currency_field='company_currency')
    re_budget_max = fields.Monetary('Budget up to', currency_field='company_currency')
    re_emirate = fields.Selection(EMIRATES, string='Emirate')
    re_areas = fields.Char('Preferred areas', help='Comma-separated, e.g. Marina, JVC, Business Bay')
    re_unit_type = fields.Selection(UNIT_TYPES, string='Property type')
    re_bedrooms = fields.Integer('Bedrooms (min)')
    re_status_pref = fields.Selection(
        [('any', 'Off-plan or ready'), ('offplan', 'Off-plan'), ('ready', 'Ready')],
        string='Off-plan / ready', default='any')
    re_unit_id = fields.Many2one('re.unit', string='Enquired about', tracking=True,
                                 help='The listing the enquiry came from.')
    re_shortlist_ids = fields.Many2many('re.unit', 're_lead_unit_rel', 'lead_id', 'unit_id',
                                        string='Shortlist')
    re_match_ids = fields.Many2many('re.unit', compute='_compute_re_matches', string='Matching units')
    re_match_count = fields.Integer(compute='_compute_re_matches')

    def _re_match_domain(self):
        self.ensure_one()
        dom = [('state', '=', 'available')]
        if self.re_purpose:
            dom.append(('purpose', '=', 'rent' if self.re_purpose == 'rent' else 'sale'))
        if self.re_budget_max:
            dom.append(('price', '<=', self.re_budget_max))
        if self.re_budget_min:
            dom.append(('price', '>=', self.re_budget_min))
        if self.re_emirate:
            dom.append(('emirate', '=', self.re_emirate))
        if self.re_unit_type:
            dom.append(('unit_type', '=', self.re_unit_type))
        if self.re_bedrooms:
            dom.append(('bedrooms', '>=', self.re_bedrooms))
        if self.re_status_pref and self.re_status_pref != 'any':
            dom.append(('project_status', '=', self.re_status_pref))
        areas = [a.strip() for a in (self.re_areas or '').split(',') if a.strip()]
        if areas:
            dom += ['|'] * (len(areas) - 1) + [('community', 'ilike', a) for a in areas]
        return dom

    @api.depends('re_purpose', 're_budget_min', 're_budget_max', 're_emirate', 're_areas',
                 're_unit_type', 're_bedrooms', 're_status_pref')
    def _compute_re_matches(self):
        Unit = self.env['re.unit']
        for lead in self:
            if not lead.re_is_real_estate:
                lead.re_match_ids = Unit
                lead.re_match_count = 0
                continue
            units = Unit.search(lead._re_match_domain(), limit=50, order='price')
            lead.re_match_ids = units
            lead.re_match_count = len(units)

    def action_re_matches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Matches for %s' % (self.partner_name or self.contact_name or self.name),
            'res_model': 're.unit', 'view_mode': 'kanban,list,form',
            'domain': self._re_match_domain(),
            'context': {'re_lead_id': self.id},
        }

    @api.model
    def _re_from_portal(self, data):
        """Create a lead from a portal / webhook payload. Accepts the usual
        names: name, email, phone, message, source, listing reference."""
        def pick(*keys):
            for k in keys:
                if data.get(k):
                    return str(data[k]).strip()
            return ''
        ref = pick('reference', 'listing_reference', 'property_reference', 'ref', 'listing_id')
        unit = self.env['re.unit'].search([('reference', '=', ref)], limit=1) if ref else self.env['re.unit']
        source = (pick('source', 'portal', 'channel') or '').lower().replace(' ', '')
        portal = next((k for k, _l in PORTALS if k == source or k in source), 'other') if source else 'other'
        team = self.env['crm.team'].search([('re_is_real_estate', '=', True)], limit=1)
        contact = pick('name', 'full_name', 'client_name') or 'Portal enquiry'
        vals = {
            'type': 'opportunity',
            'name': '%s · %s' % (contact, unit.display_name if unit else dict(PORTALS)[portal]),
            'contact_name': contact,
            'email_from': pick('email', 'client_email'),
            'phone': pick('phone', 'mobile', 'client_phone'),
            'description': pick('message', 'comments', 'enquiry'),
            're_portal': portal,
            're_unit_id': unit.id,
            're_temperature': 'warm',
            'team_id': team.id,
            'company_id': team.company_id.id or False,
        }
        if unit:
            vals.update({
                're_unit_type': unit.unit_type, 're_emirate': unit.emirate,
                're_bedrooms': unit.bedrooms, 're_purpose': 'rent' if unit.purpose == 'rent' else 'buy',
                're_shortlist_ids': [(4, unit.id)],
            })
        lead = self.create(vals)
        lead.message_post(body='Enquiry received from %s%s.' % (
            dict(PORTALS)[portal], ' on listing %s' % unit.reference if unit else ''))
        return lead

    def action_re_proposal(self):
        self.ensure_one()
        if not self.re_shortlist_ids:
            raise UserError('Add units to the shortlist first (Matches → Shortlist).')
        return self.env.ref('aabaan_real_estate.action_report_re_proposal').report_action(self)


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    re_is_real_estate = fields.Boolean('Real estate team')


class ReUnitShortlist(models.Model):
    _inherit = 're.unit'

    in_shortlist = fields.Boolean(compute='_compute_in_shortlist')
    shortlist_mode = fields.Boolean(compute='_compute_in_shortlist')

    @api.depends_context('re_lead_id')
    def _compute_in_shortlist(self):
        lead_id = self.env.context.get('re_lead_id')
        for u in self:
            u.shortlist_mode = bool(lead_id)
            u.in_shortlist = bool(lead_id) and lead_id in u.lead_ids.ids

    def action_toggle_shortlist(self):
        lead = self.env['crm.lead'].browse(self.env.context.get('re_lead_id'))
        if not lead:
            raise UserError('Open the units from a lead (Matches) to shortlist them.')
        for u in self:
            if u in lead.re_shortlist_ids:
                lead.re_shortlist_ids = [(3, u.id)]
            else:
                lead.re_shortlist_ids = [(4, u.id)]
        return True
