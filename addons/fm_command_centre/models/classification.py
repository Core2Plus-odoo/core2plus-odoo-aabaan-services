# -*- coding: utf-8 -*-
"""What the CEO dashboard needs to know about every record it counts:
which revenue stream (AMC contract or one-time cash job), which service,
and which branch.

None of the three is reliably on the records today. The invoices were
imported without a sale-order link, a branch or an analytic tag, so each
is derived here from what the records *do* carry (product names, the
customer's contracts, the customer's city) and stored, so the dashboard
can group by it in SQL. Every one of them is ``readonly=False``: the
derivation is a default, and Accounts can correct any single record
(or any product, under Command Centre → Configuration) by hand.
"""
import re

from odoo import api, fields, models

STREAMS = [('amc', 'AMC'), ('cash', 'Cash Sale')]

# The client's service list (CEO dashboard PDF, page 6) plus the three
# lines the books actually carry that the PDF does not list.
SERVICES = [
    ('pest', 'Pest Control'),
    ('termite', 'Anti-Termite'),
    ('tank', 'Tank Cleaning'),
    ('fumigation', 'Fumigation'),
    ('villa', 'Villa Cleaning'),
    ('ac', 'AC Services'),
    ('flat', 'Flat Cleaning'),
    ('sofa', 'Sofa Cleaning'),
    ('carpet', 'Carpet Cleaning'),
    ('painting', 'Painting'),
    ('mattress', 'Mattress Cleaning'),
    ('landscaping', 'Landscaping'),
    ('handyman', 'Handyman'),
    ('electrical', 'Electrical'),
    ('tile', 'Tile Fixing'),
    ('plumbing', 'Plumbing'),
    ('cleaning', 'General & Deep Cleaning'),
    ('lab', 'Lab Tests & Attestation'),
    ('project', 'Projects'),
    ('other', 'Other'),
]

# First match wins, so the specific words come before the general ones:
# "PEST CONTROL ATTESTATION" is an attestation fee, not pest control, and
# "Water Tank Cleaning" is tank cleaning, not general cleaning.
SERVICE_KEYWORDS = [
    ('lab', ('attest', 'lab test', 'laboratory', 'municipality', 'permit')),
    ('project', ('project',)),
    ('termite', ('termite',)),
    ('fumigation', ('fumigat',)),
    ('tank', ('tank',)),
    ('sofa', ('sofa', 'upholster')),
    ('carpet', ('carpet',)),
    ('mattress', ('mattress',)),
    ('villa', ('villa',)),
    ('flat', ('flat', 'apartment')),
    ('ac', ('a/c', 'hvac', 'air condition', 'ac service', 'ac maint')),
    ('painting', ('paint',)),
    ('landscaping', ('landscap', 'garden')),
    ('handyman', ('handyman',)),
    ('electrical', ('electric',)),
    ('tile', ('tile',)),
    ('plumbing', ('plumb', 'sanitary')),
    ('pest', ('pest', 'bed bug', 'rodent', 'cockroach')),
    ('cleaning', ('clean', 'janitor', 'disinfect', 'fogging')),
]

# How an emirate is spelled in product names and customer addresses.
EMIRATE_KEYWORDS = {
    'ajman': ('ajman', 'nuaimiya', 'nuaimia', 'rawdha', 'rashidiya', 'jurf'),
    'dubai': ('dubai', 'muteena', 'deira', 'bur dubai'),
    'sharjah': ('sharjah', 'shj'),
    'fujairah': ('fujairah', 'fujerah', 'fujeirah'),
    'abu_dhabi': ('abu dhabi',),
    'ras_al_khaimah': ('ras al khaimah', 'rak'),
    'umm_al_quwain': ('umm al quwain', 'uaq'),
}


def guess_service(name):
    text = (name or '').casefold()
    for key, words in SERVICE_KEYWORDS:
        if any(word in text for word in words):
            return key
    return 'other'


def guess_emirate(*texts):
    for text in texts:
        text = (text or '').casefold()
        if not text:
            continue
        for emirate, words in EMIRATE_KEYWORDS.items():
            for word in words:
                if re.search(r'(^|[^a-z])%s([^a-z]|$)' % re.escape(word), text):
                    return emirate
    return False


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    fm_cc_stream = fields.Selection(
        STREAMS, string='Revenue Stream',
        compute='_compute_fm_cc_classification', store=True, readonly=False,
        help='Which side of the CEO dashboard this product\'s sales count '
             'on. Blank = decided per invoice from the customer: a customer '
             'with a confirmed contract is AMC, anyone else a cash sale.')
    fm_cc_service = fields.Selection(
        SERVICES, string='Dashboard Service',
        compute='_compute_fm_cc_classification', store=True, readonly=False,
        help='The service this product is reported under on the CEO '
             'dashboard. Guessed from the product name; correct it here.')

    @api.depends('name')
    def _compute_fm_cc_classification(self):
        for tmpl in self:
            name = (tmpl.name or '').casefold()
            tmpl.fm_cc_service = guess_service(name)
            if 'cash' in name:
                tmpl.fm_cc_stream = 'cash'
            elif (any(w in name for w in ('contract', 'amc', 'annual'))
                    or tmpl.recurring_invoice):
                tmpl.fm_cc_stream = 'amc'
            else:
                tmpl.fm_cc_stream = False

    def _fm_cc_mark_contract_products(self):
        """A product sold on a confirmed FM contract is a contract product.
        Run once on install: it reads order lines, which a name-only
        compute cannot depend on. Fees and lab tests are left alone — they
        are sold on contracts and to walk-in customers alike."""
        lines = self.env['sale.order.line'].search([
            ('order_id.state', '=', 'sale'),
            ('product_id', '!=', False)])
        if 'is_fm_contract' in self.env['sale.order']._fields:
            lines = lines.filtered(lambda l: l.order_id.is_fm_contract)
        tmpls = lines.product_id.product_tmpl_id.filtered(
            lambda t: not t.fm_cc_stream
            and t.fm_cc_service not in ('lab', 'other'))
        tmpls.write({'fm_cc_stream': 'amc'})
        return tmpls


class FmBranch(models.Model):
    _inherit = 'fm.branch'

    amc_monthly_target = fields.Monetary(
        string='AMC Monthly Target', currency_field='currency_id',
        help='AMC (contract) revenue this branch should invoice in a '
             'calendar month, excluding VAT. Zero = no target shown.')
    cash_monthly_target = fields.Monetary(
        string='Cash Sales Monthly Target', currency_field='currency_id',
        help='One-time job revenue this branch should invoice in a '
             'calendar month, excluding VAT. Zero = no target shown.')
    emirate_label = fields.Char(compute='_compute_emirate_label')

    def _compute_emirate_label(self):
        for branch in self:
            branch.emirate_label = (branch.name or '').split(' — ')[-1]


class FmCcSalesTarget(models.Model):
    """Monthly deal target per salesperson. Its own model rather than a
    field on res.users: extending res.users makes every upgrade of this
    module run res.users.init(), which can write to users before the other
    new columns of the module exist."""
    _name = 'fm.cc.sales.target'
    _description = 'CEO Dashboard — salesperson target'
    _order = 'user_id'

    user_id = fields.Many2one(
        'res.users', string='Salesperson', required=True, ondelete='cascade',
        domain=[('share', '=', False)])
    deal_target = fields.Integer(
        string='Monthly Deals Target',
        help='Deals (AMC contracts started + cash jobs invoiced) this person '
             'should close in a month.')

    _user_unique = models.Constraint(
        'UNIQUE(user_id)', 'Each salesperson has one target.')


class ResCompany(models.Model):
    _inherit = 'res.company'

    fm_cc_margin_target = fields.Float(
        string='Net Margin Target (%)', default=22.0)
    fm_cc_tagline = fields.Char(
        string='Dashboard Tagline', default='One Stop for Every Service Need!')


def _branch_by_emirate(env):
    out = {}
    for branch in env['fm.branch'].search([]):
        emirate = branch.emirate or guess_emirate(branch.name, branch.city)
        if emirate and emirate not in out:
            out[emirate] = branch.id
    return out


# x_emirate_regime (Studio) values on the contract
REGIME_EMIRATE = {'ajman': 'ajman', 'dubai': 'dubai', 'sharjah': 'sharjah',
                  'fujairah': 'fujairah', 'Fujairah': 'fujairah'}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    fm_cc_branch_id = fields.Many2one(
        'fm.branch', string='Dashboard Branch', index=True,
        compute='_compute_fm_cc_branch', store=True, readonly=False,
        help='Branch this contract counts under on the CEO dashboard: its '
             'Branch, else its emirate regime, else the customer\'s city.')

    @api.depends('branch_id', 'partner_id.city', 'partner_id.state_id')
    def _compute_fm_cc_branch(self):
        by_emirate = _branch_by_emirate(self.env)
        for order in self:
            branch = order.branch_id.id if 'branch_id' in order._fields else False
            if not branch:
                regime = order['x_emirate_regime'] \
                    if 'x_emirate_regime' in order._fields else False
                emirate = REGIME_EMIRATE.get(regime) or guess_emirate(
                    order.partner_id.city, order.partner_id.state_id.name,
                    order.partner_id.street2)
                branch = by_emirate.get(emirate, False)
            order.fm_cc_branch_id = branch


class AccountMove(models.Model):
    _inherit = 'account.move'

    fm_cc_stream = fields.Selection(
        STREAMS, string='Revenue Stream', index=True,
        compute='_compute_fm_cc_stream', store=True, readonly=False,
        help='AMC (contract) or Cash Sale (one-time job), for the CEO '
             'dashboard. Derived from the sale order, then the products, '
             'then whether the customer holds a confirmed contract.')
    fm_cc_branch_id = fields.Many2one(
        'fm.branch', string='Dashboard Branch', index=True,
        compute='_compute_fm_cc_branch', store=True, readonly=False,
        help='Branch this document counts under on the CEO dashboard: its '
             'Branch, else its sale order\'s, else the emirate in the '
             'product name, else the customer\'s city.')

    fm_cc_service = fields.Selection(
        SERVICES, string='Dashboard Service', index=True,
        compute='_compute_fm_cc_service', store=True,
        help='The service this invoice counts under on the CEO dashboard\'s '
             'service filter: the service of its largest line, so every '
             'invoice belongs to exactly one service and the services add '
             'up to the total.')

    @api.depends('invoice_line_ids.fm_cc_service', 'invoice_line_ids.price_subtotal',
                 'invoice_line_ids.display_type')
    def _compute_fm_cc_service(self):
        for move in self:
            lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.fm_cc_service)
            if not lines:
                move.fm_cc_service = False
                continue
            totals = {}
            for line in lines:
                totals[line.fm_cc_service] = totals.get(line.fm_cc_service, 0.0) \
                    + abs(line.price_subtotal)
            move.fm_cc_service = max(totals, key=totals.get)

    @api.depends('move_type', 'partner_id', 'invoice_line_ids.product_id',
                 'invoice_line_ids.product_id.fm_cc_stream')
    def _compute_fm_cc_stream(self):
        contract_partners = set()
        customers = self.filtered(lambda m: m.is_sale_document(include_receipts=True))
        if customers:
            orders = self.env['sale.order'].search([
                ('state', '=', 'sale'),
                ('partner_id.commercial_partner_id', 'in',
                 customers.partner_id.commercial_partner_id.ids)])
            contract_partners = set(
                orders.partner_id.commercial_partner_id.ids)
        for move in self:
            if not move.is_sale_document(include_receipts=True):
                move.fm_cc_stream = False
                continue
            orders = move.invoice_line_ids.sale_line_ids.order_id
            if orders:
                is_contract = any(
                    o.is_fm_contract if 'is_fm_contract' in o._fields
                    else o.is_subscription for o in orders)
                move.fm_cc_stream = 'amc' if is_contract else 'cash'
                continue
            streams = set(move.invoice_line_ids.product_id
                          .product_tmpl_id.mapped('fm_cc_stream'))
            if 'amc' in streams:
                move.fm_cc_stream = 'amc'
            elif 'cash' in streams:
                move.fm_cc_stream = 'cash'
            elif move.partner_id.commercial_partner_id.id in contract_partners:
                move.fm_cc_stream = 'amc'
            else:
                move.fm_cc_stream = 'cash'

    @api.depends('branch_id', 'partner_id.city', 'partner_id.state_id',
                 'invoice_line_ids.product_id')
    def _compute_fm_cc_branch(self):
        by_emirate = _branch_by_emirate(self.env)
        pending = self.env['account.move']
        for move in self:
            branch = move.branch_id.id
            if not branch:
                orders = move.invoice_line_ids.sale_line_ids.order_id
                branch = orders[:1].fm_cc_branch_id.id
            if not branch:
                emirate = guess_emirate(
                    *move.invoice_line_ids.product_id.mapped('name'))
                emirate = emirate or guess_emirate(
                    move.partner_id.city, move.partner_id.state_id.name,
                    move.partner_id.street2)
                branch = by_emirate.get(emirate, False)
            move.fm_cc_branch_id = branch
            if not branch and move.is_sale_document(include_receipts=True):
                pending |= move
        if pending:
            partner_branch = self._fm_cc_partner_branches(
                pending.commercial_partner_id, by_emirate)
            for move in pending:
                move.fm_cc_branch_id = partner_branch.get(
                    move.commercial_partner_id.id, False)

    @api.model
    def _fm_cc_partner_branches(self, partners, by_emirate):
        """Where a customer is served, for an invoice that says nothing about
        it: the branch of the customer's contract, else the emirate named
        most often in the products on the customer's other invoices."""
        out = {}
        if not partners:
            return out
        for order in self.env['sale.order'].search([
                ('state', '=', 'sale'), ('fm_cc_branch_id', '!=', False),
                ('partner_id.commercial_partner_id', 'in', partners.ids)]):
            out.setdefault(order.partner_id.commercial_partner_id.id,
                           order.fm_cc_branch_id.id)
        rest = [p for p in partners.ids if p not in out]
        if rest:
            votes = {}
            lines = self.env['account.move.line'].search([
                ('move_id.commercial_partner_id', 'in', rest),
                ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
                ('product_id', '!=', False)])
            for line in lines:
                emirate = guess_emirate(line.product_id.name)
                branch = by_emirate.get(emirate)
                if branch:
                    pid = line.move_id.commercial_partner_id.id
                    votes.setdefault(pid, {}).setdefault(branch, 0)
                    votes[pid][branch] += 1
            for pid, counts in votes.items():
                out[pid] = max(counts, key=counts.get)
        return out


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    fm_cc_service = fields.Selection(
        string='Dashboard Service', index=True,
        related='product_id.product_tmpl_id.fm_cc_service', store=True)
    fm_cc_stream = fields.Selection(
        related='move_id.fm_cc_stream', store=True,
        string='Revenue Stream')
    fm_cc_branch_id = fields.Many2one(
        'fm.branch', related='move_id.fm_cc_branch_id', store=True,
        string='Dashboard Branch')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    fm_cc_branch_id = fields.Many2one(
        'fm.branch', string='Dashboard Branch', index=True,
        compute='_compute_fm_cc_branch', store=True, readonly=False)

    @api.depends('branch_id', 'sale_order_id.fm_cc_branch_id')
    def _compute_fm_cc_branch(self):
        for task in self:
            branch = task.branch_id if 'branch_id' in task._fields else False
            if not branch and 'fm_contract_order_id' in task._fields:
                branch = task.fm_contract_order_id.fm_cc_branch_id
            task.fm_cc_branch_id = branch or task.sale_order_id.fm_cc_branch_id
