# -*- coding: utf-8 -*-
from odoo import api, fields, models

UNIT_TYPES = [
    ('apartment', 'Apartment'), ('studio', 'Studio'), ('penthouse', 'Penthouse'),
    ('townhouse', 'Townhouse'), ('villa', 'Villa'), ('office', 'Office'),
    ('retail', 'Retail'), ('plot', 'Plot'),
]


class ReUnit(models.Model):
    _name = 're.unit'
    _description = 'Property Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, price, name'

    name = fields.Char('Unit', required=True, tracking=True)
    active = fields.Boolean(default=True)
    project_id = fields.Many2one('re.project', index=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    developer_id = fields.Many2one(related='project_id.developer_id', store=True)
    emirate = fields.Selection(related='project_id.emirate', store=True)
    community = fields.Char(related='project_id.community', store=True)
    project_status = fields.Selection(related='project_id.status', store=True, string='Off-plan / Ready')
    handover_date = fields.Date(related='project_id.handover_date', store=True)
    image = fields.Image(max_width=1920, max_height=1920)
    image_512 = fields.Image(related='image', max_width=512, max_height=512, store=True)
    cover = fields.Image(compute='_compute_cover', max_width=512, max_height=512)
    purpose = fields.Selection([('sale', 'For sale'), ('rent', 'For rent')], default='sale', required=True)
    unit_type = fields.Selection(UNIT_TYPES, default='apartment', required=True)
    bedrooms = fields.Integer()
    bathrooms = fields.Integer()
    size_sqft = fields.Float('Size (sq ft)')
    floor = fields.Char()
    view = fields.Char()
    price = fields.Monetary(tracking=True)
    price_per_sqft = fields.Monetary(compute='_compute_price_per_sqft', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    permit_number = fields.Char('Permit (Trakheesi) No.')
    # listing on the portals
    reference = fields.Char('Listing Ref.', copy=False, index=True, readonly=True, default='/')
    listing_title = fields.Char()
    listing_description = fields.Text()
    agent_id = fields.Many2one('res.users', string='Listing agent', default=lambda s: s.env.user)
    publish_bayut = fields.Boolean('Bayut')
    publish_propertyfinder = fields.Boolean('Property Finder')
    publish_dubizzle = fields.Boolean('Dubizzle')
    published = fields.Boolean(compute='_compute_published', store=True)
    gallery_ids = fields.One2many('re.unit.image', 'unit_id', string='Photos')
    lead_count = fields.Integer(compute='_compute_lead_count')
    state = fields.Selection([
        ('available', 'Available'), ('reserved', 'Reserved'), ('sold', 'Sold'), ('rented', 'Rented'),
    ], default='available', required=True, tracking=True, group_expand=True)
    lead_ids = fields.Many2many('crm.lead', 're_lead_unit_rel', 'unit_id', 'lead_id', string='Shortlisted for')
    beds_label = fields.Char(compute='_compute_beds_label')

    _reference_unique = models.Constraint('UNIQUE(reference)', 'Listing references must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', '/') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code('re.unit.reference') or '/'
        return super().create(vals_list)

    @api.depends('publish_bayut', 'publish_propertyfinder', 'publish_dubizzle', 'state')
    def _compute_published(self):
        for u in self:
            u.published = u.state == 'available' and (
                u.publish_bayut or u.publish_propertyfinder or u.publish_dubizzle)

    def _compute_lead_count(self):
        groups = self.env['crm.lead']._read_group(
            [('re_unit_id', 'in', self.ids)], ['re_unit_id'], ['__count'])
        counts = {unit.id: n for unit, n in groups}
        for u in self:
            u.lead_count = counts.get(u.id, 0)

    def action_leads(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Enquiries · %s' % self.display_name,
            'res_model': 'crm.lead', 'view_mode': 'list,kanban,form',
            'domain': ['|', ('re_unit_id', '=', self.id), ('re_shortlist_ids', 'in', self.id)],
        }

    @api.depends('price', 'size_sqft')
    def _compute_price_per_sqft(self):
        for u in self:
            u.price_per_sqft = u.price / u.size_sqft if u.size_sqft else 0.0

    @api.depends('image', 'project_id.image')
    def _compute_cover(self):
        for u in self:
            u.cover = u.image or u.project_id.image

    @api.depends('bedrooms', 'unit_type')
    def _compute_beds_label(self):
        for u in self:
            if u.unit_type == 'studio':
                u.beds_label = 'Studio'
            elif u.bedrooms:
                u.beds_label = '%d BR' % u.bedrooms
            else:
                u.beds_label = ''

    @api.depends('name', 'project_id.name')
    def _compute_display_name(self):
        for u in self:
            u.display_name = '%s · %s' % (u.project_id.name, u.name) if u.project_id else u.name


class ReUnitImage(models.Model):
    _name = 're.unit.image'
    _description = 'Unit Photo'
    _order = 'sequence, id'

    unit_id = fields.Many2one('re.unit', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char()
    image = fields.Image(required=True, max_width=1920, max_height=1920)
