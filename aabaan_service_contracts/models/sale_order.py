# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    contract_site_ids = fields.One2many(
        'aabaan.contract.site', 'order_id', string="Sites")
    contract_document_ids = fields.One2many(
        'aabaan.contract.document', 'order_id', string="Compliance Documents")
    contract_sites_count = fields.Integer(
        string="Site Count", compute='_compute_contract_rollups')
    contract_documents_count = fields.Integer(
        string="Document Count", compute='_compute_documents_count')
    contract_avg_uptime = fields.Float(
        string="Avg. SLA Uptime YTD (%)", compute='_compute_contract_rollups',
        digits=(5, 1),
        help="Visit-weighted average across all sites — a site with more "
             "visit history counts more. 0 until visits exist.")
    contract_notice_period_days = fields.Integer(
        string="Renewal Notice Period (days)", default=90,
        help="From the signed agreement. Defaults to 90 to match the "
             "renewal window used elsewhere in the Contract Cockpit — "
             "confirm against the actual agreement and correct if different.")
    contract_indexation_clause = fields.Selection([
        ('none', 'None'),
        ('cpi_linked', 'CPI-Linked'),
    ], string="Indexation Clause", default='none')
    contract_indexation_cap_pct = fields.Float(
        string="Indexation Cap (%)",
        help="Maximum annual uplift under the CPI clause, if any. "
             "The indicative uplift amount is not auto-calculated — this "
             "database has no live UAE CPI rate source, and estimating one "
             "would be an invented number.")

    @api.depends('contract_document_ids')
    def _compute_documents_count(self):
        for order in self:
            order.contract_documents_count = len(order.contract_document_ids)

    def action_view_contract_sites(self):
        """Smart button: this contract's Sites & SLA lines in a standalone
        list (the embedded list's site picker domain references the parent
        order, so it cannot be reused outside the order form)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Sites — %s" % self.name,
            'res_model': 'aabaan.contract.site',
            'domain': [('order_id', '=', self.id)],
            'views': [
                (self.env.ref(
                    'aabaan_service_contracts.view_contract_site_list_full').id,
                 'list'),
                (False, 'form')],
            'context': {'default_order_id': self.id},
        }

    def action_view_contract_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Compliance Documents — %s" % self.name,
            'res_model': 'aabaan.contract.document',
            'domain': [('order_id', '=', self.id)],
            'views': [
                (self.env.ref(
                    'aabaan_service_contracts.view_contract_document_list_full').id,
                 'list'),
                (False, 'form')],
            'context': {'default_order_id': self.id},
        }

    @api.depends('contract_site_ids.uptime_ytd', 'contract_site_ids.visit_count_ytd')
    def _compute_contract_rollups(self):
        for order in self:
            sites = order.contract_site_ids
            order.contract_sites_count = len(sites)
            total_visits = sum(sites.mapped('visit_count_ytd'))
            if total_visits:
                weighted = sum(
                    site.uptime_ytd * site.visit_count_ytd for site in sites)
                order.contract_avg_uptime = round(weighted / total_visits, 1)
            else:
                order.contract_avg_uptime = 0.0


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    site_id = fields.Many2one(
        'res.partner', string="Site",
        help="Which of the contract's sites this line belongs to — feeds "
             "the per-site value on the Sites & Compliance tab. Leave "
             "blank for lines that apply to the whole contract.")
