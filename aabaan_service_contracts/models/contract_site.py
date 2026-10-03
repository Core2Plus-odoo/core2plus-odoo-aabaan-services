# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import datetime, time

from odoo import api, fields, models


class AabaanContractSite(models.Model):
    """One row per site covered by a master contract — the 'Sites & SLA'
    breakdown from the approved UI reference. Every number here is derived
    from real visit/order-line data; nothing is invented (no assumed
    monthly-billing cadence, no fabricated SLA percentages)."""
    _name = 'aabaan.contract.site'
    _description = "Contract Site & SLA Line"
    _order = 'id'

    order_id = fields.Many2one(
        'sale.order', string="Contract", required=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='order_id.company_id', store=True)
    currency_id = fields.Many2one(
        related='order_id.currency_id', store=True)
    site_id = fields.Many2one(
        'res.partner', string="Site / Location", required=True,
        help="One of the customer's site contacts (Locations smart button "
             "on the customer, or Contacts tab on this order's customer).")
    service_tag_ids = fields.Many2many(
        'aabaan.service.tag', string="Services",
        help="What is delivered at this site — Pest Control, Cleaning, "
             "AC Duct, etc. Independent of the order lines below; used for "
             "the at-a-glance site breakdown.")
    frequency = fields.Char(
        string="Frequency",
        help="As agreed for this site, e.g. \"Daily + Weekly\", "
             "\"Bi-weekly\", \"On-demand\".")
    sla_response_target = fields.Char(
        string="SLA Response Target",
        help="From the signed agreement, e.g. \"≤ 4 hours\".")
    status = fields.Selection([
        ('active', 'Active'),
        ('review', 'Under Review'),
        ('suspended', 'Suspended'),
    ], default='active', required=True)
    visit_count_ytd = fields.Integer(
        string="Visits YTD", compute='_compute_site_metrics')
    uptime_ytd = fields.Float(
        string="SLA Uptime YTD (%)", compute='_compute_site_metrics',
        digits=(5, 1),
        help="Share of this site's visits this calendar year that were NOT "
             "SLA-escalated. Blank/0 until the site has visit history — "
             "never estimated.")
    site_value = fields.Monetary(
        string="Site Value (Contract Term)", compute='_compute_site_metrics',
        currency_field='currency_id',
        help="Sum of this order's lines tagged to this site (see the Site "
             "column on Order Lines). Shown for the whole contract term, "
             "not converted to a monthly figure — billing cadence varies "
             "by contract and a forced /month conversion would not be a "
             "real number.")

    @api.depends('order_id', 'site_id', 'order_id.order_line.site_id',
                 'order_id.order_line.price_subtotal')
    def _compute_site_metrics(self):
        Task = self.env['project.task']
        now = fields.Datetime.now()
        year_start = fields.Datetime.to_string(datetime.combine(
            fields.Date.context_today(self).replace(month=1, day=1),
            time.min))
        has_planned = 'planned_date_begin' in Task._fields
        for line in self:
            visits = escalated = 0
            if line.order_id.id and line.site_id.id:
                domain = [
                    ('sale_order_id', '=', line.order_id.id),
                    ('partner_id', '=', line.site_id.id),
                    ('project_id.is_fsm', '=', True),
                ]
                # Only visits already DUE count toward a track record — a
                # visit scheduled for next month hasn't proven anything
                # yet, so including it would inflate uptime artificially.
                # Mirrors the due/overdue distinction in Contract Cockpit.
                if has_planned:
                    domain += [('planned_date_begin', '>=', year_start),
                              ('planned_date_begin', '<',
                               fields.Datetime.to_string(now))]
                tasks = Task.search(domain)
                visits = len(tasks)
                escalated = sum(1 for task in tasks if task.sla_escalated)
            line.visit_count_ytd = visits
            line.uptime_ytd = (
                round(100.0 * (1 - escalated / visits), 1) if visits else 0.0)
            site_lines = line.order_id.order_line.filtered(
                lambda l: l.site_id == line.site_id and not l.display_type)
            line.site_value = sum(site_lines.mapped('price_subtotal'))
