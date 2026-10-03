# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    aabaan_area = fields.Char(
        string="Area / District", index=True,
        help="The area the premises sit in (Al Nuaimiya, Al Rashidiya 2, "
             "Abu Hail, ...). Set it on each location contact — visit "
             "routing groups by it.")
    aabaan_location_count = fields.Integer(
        string="Locations", compute='_compute_aabaan_location_count')

    def _compute_aabaan_location_count(self):
        groups = {}
        parents = self.filtered(lambda p: p.id)
        if parents:
            groups = {
                parent.id: count
                for parent, count in self.env['res.partner']._read_group(
                    [('parent_id', 'in', parents.ids)],
                    ['parent_id'], ['__count'])
            }
        for partner in self:
            partner.aabaan_location_count = groups.get(partner.id, 0)

    def action_view_locations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Locations of %s") % self.name,
            'res_model': 'res.partner',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id,
                        'default_type': 'delivery',
                        'default_is_company': False},
            'views': [(False, 'list'), (False, 'form')],
            'target': 'current',
        }


class ProjectTask(models.Model):
    _inherit = 'project.task'

    aabaan_area = fields.Char(
        string="Area / District", related='partner_id.aabaan_area',
        store=True, readonly=True,
        help="From the visit's contact — group the dispatch board by it "
             "to build technician routes.")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # In a service business the "delivery" address IS the site being
    # serviced — relabel it everywhere (form, lists, filters, exports) and
    # offer only the chosen client's own sites, not the whole address book.
    partner_shipping_id = fields.Many2one(
        string="Site Address",
        domain="[('id', 'child_of', partner_id)]",
        help="The location being serviced under this contract — one of the "
             "client's site contacts (pick the customer first). Visits, "
             "area routing and the emirate tagging all follow it.")

    aabaan_site_area = fields.Char(
        string="Site Area", related='partner_shipping_id.aabaan_area',
        readonly=True,
        help="Area of the site address on this contract.")


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_shipping_id = fields.Many2one(
        string="Site Address",
        domain="[('id', 'child_of', partner_id)]")
