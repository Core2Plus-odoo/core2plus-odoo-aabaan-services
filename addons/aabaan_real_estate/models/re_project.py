# -*- coding: utf-8 -*-
from odoo import api, fields, models

def short_aed(value):
    if not value:
        return ''
    if value >= 1_000_000:
        return 'AED %sM' % ('%.2f' % (value / 1_000_000)).rstrip('0').rstrip('.')
    if value >= 1_000:
        return 'AED %sK' % ('%.1f' % (value / 1_000)).rstrip('0').rstrip('.')
    return 'AED %d' % value


EMIRATES = [
    ('dubai', 'Dubai'), ('abu_dhabi', 'Abu Dhabi'), ('sharjah', 'Sharjah'),
    ('ajman', 'Ajman'), ('rak', 'Ras Al Khaimah'), ('uaq', 'Umm Al Quwain'),
    ('fujairah', 'Fujairah'),
]


class ReProject(models.Model):
    _name = 're.project'
    _description = 'Property Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, handover_date, name'

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda s: s._re_default_company(), index=True)
    developer_id = fields.Many2one('re.developer', tracking=True)
    image = fields.Image('Cover photo', max_width=1920, max_height=1920)
    image_512 = fields.Image(related='image', max_width=512, max_height=512, store=True)
    emirate = fields.Selection(EMIRATES, default='dubai', required=True)
    community = fields.Char('Area / Community', tracking=True)
    status = fields.Selection([('offplan', 'Off-plan'), ('ready', 'Ready')],
                              default='offplan', required=True, tracking=True)
    handover_date = fields.Date(tracking=True)
    description = fields.Html()
    amenity_ids = fields.Many2many('re.amenity', string='Amenities')
    nearby = fields.Char(help='Metro, schools, malls nearby.')
    map_url = fields.Char('Map link')
    brochure = fields.Binary(attachment=True)
    brochure_name = fields.Char()
    payment_plan_ids = fields.One2many('re.payment.plan.line', 'project_id', copy=True)
    payment_plan_summary = fields.Char(compute='_compute_payment_plan_summary')
    booking_percent = fields.Float(compute='_compute_payment_plan_summary')
    unit_ids = fields.One2many('re.unit', 'project_id')
    unit_count = fields.Integer(compute='_compute_units', store=True)
    available_count = fields.Integer(compute='_compute_units', store=True)
    available_rate = fields.Float(compute='_compute_units', store=True)
    price_from = fields.Monetary(compute='_compute_units', store=True, aggregator='min')
    price_to = fields.Monetary(compute='_compute_units', store=True, aggregator='max')
    unit_types = fields.Char(compute='_compute_units', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda s: s._re_default_company().currency_id)
    color = fields.Integer()
    price_label = fields.Char(compute='_compute_labels')
    handover_label = fields.Char(compute='_compute_labels')

    @api.depends('price_from', 'handover_date')
    def _compute_labels(self):
        for p in self:
            p.price_label = short_aed(p.price_from)
            p.handover_label = p.handover_date.strftime('%b %Y') if p.handover_date else ''

    @api.model
    def _re_default_company(self):
        """Aabaan Real Estate is its own company: new projects go to the
        company of the real-estate sales team, whichever company the user
        happens to be working in."""
        team = self.env.ref('aabaan_real_estate.crm_team_real_estate', raise_if_not_found=False)
        company = team.sudo().company_id if team else False
        if company and company in self.env.user.company_ids:
            return company
        return self.env.company

    @api.depends('payment_plan_ids.percent', 'payment_plan_ids.name')
    def _compute_payment_plan_summary(self):
        for p in self:
            lines = p.payment_plan_ids.sorted('sequence')
            p.payment_plan_summary = ' / '.join('%g' % l.percent for l in lines) if lines else ''
            p.booking_percent = lines[:1].percent if lines else 0.0

    @api.depends('unit_ids.state', 'unit_ids.price', 'unit_ids.unit_type')
    def _compute_units(self):
        labels = dict(self.env['re.unit']._fields['unit_type'].selection)
        for p in self:
            units = p.unit_ids
            avail = units.filtered(lambda u: u.state == 'available')
            p.unit_count = len(units)
            p.available_count = len(avail)
            p.available_rate = 100.0 * len(avail) / len(units) if units else 0.0
            prices = (avail or units).mapped('price')
            prices = [x for x in prices if x]
            p.price_from = min(prices) if prices else 0.0
            p.price_to = max(prices) if prices else 0.0
            types = []
            for t in units.mapped('unit_type'):
                if t and labels.get(t) not in types:
                    types.append(labels.get(t))
            p.unit_types = ', '.join(types)

    def action_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.name,
            'res_model': 're.unit', 'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_compare(self):
        return self.env.ref('aabaan_real_estate.action_report_re_compare').report_action(self[:4])


class RePaymentPlanLine(models.Model):
    _name = 're.payment.plan.line'
    _description = 'Payment Plan Milestone'
    _order = 'sequence, id'

    project_id = fields.Many2one('re.project', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char('Milestone', required=True, help='e.g. On booking, During construction, On handover')
    percent = fields.Float('%', required=True)


class ReAmenity(models.Model):
    _name = 're.amenity'
    _description = 'Amenity'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    color = fields.Integer()
