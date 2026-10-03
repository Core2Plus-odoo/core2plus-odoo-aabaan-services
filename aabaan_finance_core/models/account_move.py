# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Finance requirements §4.1: everything outstanding up to 31 Jul 2026 is
# "Previous Recovery" — the company-history cutoff, never mixed with current.
RECOVERY_CUTOFF = date(2026, 8, 1)


class AccountMove(models.Model):
    _inherit = 'account.move'

    recovery_bucket = fields.Selection([
        ('previous', 'Previous Recovery'),
        ('current', 'Current Recovery'),
        ('future', 'Future Due'),
    ], compute='_compute_recovery_bucket', store=True,
        help="Previous: due before 1 Aug 2026 (company-history cutoff). "
             "Current: due this calendar month. Future: due later. "
             "Refreshed daily.")
    recovery_status = fields.Selection([
        ('under_recovery', 'Under Recovery'),
        ('payment_promised', 'Payment Promised'),
    ], string="Recovery Status", copy=False, tracking=True,
        help="Manual collection status; Partially/Fully Paid and Overdue "
             "come from the payment state and due date.")
    recovery_promise_date = fields.Date(string="Promised Date", copy=False)
    aabaan_services = fields.Char(
        string="Services", store=True, compute='_compute_aabaan_services',
        help="All services on the contracts behind this invoice — the "
             "service dimension of the recovery grid (§5).")
    aabaan_analytic_incomplete = fields.Boolean(
        string="Untagged for Branch", store=True, readonly=True,
        compute='_compute_aabaan_analytic_incomplete',
        help="This posted entry has a line that should carry a branch (and "
             "for customer invoices a service) analytic tag and does not, so "
             "its amount is missing from the branch P&L. Set the analytic "
             "distribution on the line and the flag clears itself.")

    @api.depends('invoice_line_ids.sale_line_ids')
    def _compute_aabaan_services(self):
        line_has_sale = 'sale_line_ids' in self.env['account.move.line']._fields
        for move in self:
            names = []
            if line_has_sale and move.move_type in ('out_invoice', 'out_refund'):
                for order in move.invoice_line_ids.sale_line_ids.order_id:
                    if not hasattr(order, 'aabaan_service_names'):
                        break
                    for name in order.aabaan_service_names():
                        if name not in names:
                            names.append(name)
            move.aabaan_services = " + ".join(names)

    @api.depends('invoice_date_due', 'move_type', 'state', 'payment_state')
    def _compute_recovery_bucket(self):
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1, days=-1)
        for move in self:
            bucket = False
            if (move.move_type == 'out_invoice' and move.state == 'posted'
                    and move.payment_state in ('not_paid', 'partial')):
                due = move.invoice_date_due or move.invoice_date or today
                if due < RECOVERY_CUTOFF and due < month_start:
                    bucket = 'previous'
                elif due <= month_end:
                    bucket = 'current'
                else:
                    bucket = 'future'
            move.recovery_bucket = bucket

    @api.model
    def _cron_refresh_recovery_buckets(self):
        """Month boundaries move the buckets — recompute open invoices daily."""
        moves = self.search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial'))])
        self.env.add_to_compute(self._fields['recovery_bucket'], moves)

    # ------------------------------------------------------------------
    # Priority 1 — enforced branch/service analytic segregation
    # ------------------------------------------------------------------

    @api.model
    def _aabaan_analytic_plans(self):
        Plan = self.env['account.analytic.plan']
        emirate = Plan.search([('name', 'ilike', 'emirate')], limit=1)
        service = Plan.search([('name', 'ilike', 'service')], limit=1)
        return emirate, service

    def _aabaan_find_analytic_account(self, plan, needle):
        if not (plan and needle):
            return self.env['account.analytic.account']
        needle = str(needle).replace('_', ' ').casefold()
        for account in self.env['account.analytic.account'].search(
                [('root_plan_id', '=', plan.id)]):
            name = (account.name or '').casefold()
            if needle in name or name in needle:
                return account
        return self.env['account.analytic.account']

    def _aabaan_autofill_analytic(self, emirate_plan, service_plan):
        """Fill missing tags from the source contract before enforcing."""
        for move in self:
            for line in move.invoice_line_ids.filtered(
                    lambda l: l.display_type == 'product'):
                order = line.sale_line_ids.order_id[:1] if 'sale_line_ids' in line._fields else False
                if not order:
                    continue
                dist = dict(line.analytic_distribution or {})
                plans = self._aabaan_line_plans(dist)
                add = self.env['account.analytic.account']
                if emirate_plan and emirate_plan.id not in plans:
                    # An explicit branch on the contract beats matching the
                    # x_emirate_regime label against account names: the
                    # fuzzy step is what leaves a posting blocked when no
                    # name matches. Guarded because aabaan_finance_core does
                    # not depend on aabaan_branches.
                    branch = order.aabaan_branch_id \
                        if 'aabaan_branch_id' in order._fields \
                        else self.env['account.analytic.account']
                    if branch and branch.root_plan_id == emirate_plan:
                        add |= branch
                    else:
                        label = order._aabaan_selection_display('x_emirate_regime') \
                            if hasattr(order, '_aabaan_selection_display') else order._xval('x_emirate_regime')
                        add |= self._aabaan_find_analytic_account(emirate_plan, label)
                if service_plan and service_plan.id not in plans:
                    label = order._aabaan_selection_display('x_service_line') \
                        if hasattr(order, '_aabaan_selection_display') else order._xval('x_service_line')
                    add |= self._aabaan_find_analytic_account(service_plan, label)
                if add:
                    for account in add:
                        dist[str(account.id)] = 100
                    line.analytic_distribution = dist

    def _aabaan_line_plans(self, dist):
        ids = set()
        for key in (dist or {}):
            for part in str(key).split(','):
                if part.strip().isdigit():
                    ids.add(int(part))
        accounts = self.env['account.analytic.account'].browse(list(ids)).exists()
        return set(accounts.mapped('root_plan_id').ids)

    def _aabaan_analytic_gaps(self, emirate_plan, service_plan):
        """Lines that should carry a branch/service tag and don't.

        One matrix, read by both the posting guard and the "untagged" flag,
        so what blocks a document and what shows up in the exception queue
        can never drift apart.

        Customer invoices need branch AND service. Vendor bills need the
        branch only — overheads like utilities have no service line (§7 asks
        for Branch → Department → Expense Category, not a service). Journal
        entries need the branch on their expense lines.
        """
        self.ensure_one()
        if self.move_type in ('out_invoice', 'out_refund'):
            required = [emirate_plan, service_plan]
            lines = self.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product')
        elif self.move_type in ('in_invoice', 'in_refund'):
            required = [emirate_plan]
            lines = self.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product')
        elif self.move_type == 'entry':
            required = [emirate_plan]
            lines = self.line_ids.filtered(
                lambda l: (l.account_id.account_type or '').startswith(
                    'expense'))
        else:
            return []

        gaps = []
        for line in lines:
            plans = self._aabaan_line_plans(line.analytic_distribution)
            missing = [plan for plan in required
                       if plan and plan.id not in plans]
            if missing:
                gaps.append((line, missing))
        return gaps

    @api.depends('state', 'move_type', 'line_ids.analytic_distribution',
                 'line_ids.account_id', 'line_ids.display_type')
    def _compute_aabaan_analytic_incomplete(self):
        """Flag a posted move whose amounts cannot reach a branch total.

        This is the counterweight to not blocking journal entries: an
        untagged entry still posts, but it is never silent — it lands in
        Management Reports → Untagged for Branch until someone tags it.
        Re-tagging a posted line recomputes this, so the queue empties as
        the work is done.
        """
        emirate_plan, service_plan = self._aabaan_analytic_plans()
        for move in self:
            move.aabaan_analytic_incomplete = bool(
                move.state == 'posted'
                and (emirate_plan or service_plan)
                and move._aabaan_analytic_gaps(emirate_plan, service_plan))

    def _aabaan_check_analytic_segregation(self):
        """Block a document a person can still fix; never block the machine.

        The hard stop covers customer invoices and vendor bills only — the
        same business domains native Odoo offers a mandatory analytic
        applicability for, which this module already configures in its
        post-init hook. Native deliberately stops there, and so does this.

        Journal entries are not blocked. Almost every `entry` touching an
        expense account is machine-written — payroll, asset depreciation,
        anglo-saxon COGS, reconciliation write-offs and exchange differences
        — posted from a cron or a batch wizard with no analytic distribution
        and no screen on which anyone could add one. Raising there does not
        get the entry tagged; it aborts the payroll run, and takes the rest
        of the batch down with it in the same transaction. Those entries now
        post and are flagged instead (see aabaan_analytic_incomplete).
        """
        if self.env.context.get('aabaan_skip_analytic_check'):
            return
        if self.env['ir.config_parameter'].sudo().get_param(
                'aabaan_finance_core.enforce_analytic', '1') != '1':
            return
        emirate_plan, service_plan = self._aabaan_analytic_plans()
        if not emirate_plan and not service_plan:
            return  # plans not configured on this database — nothing to enforce
        invoices = self.filtered(lambda m: m.move_type in (
            'out_invoice', 'out_refund', 'in_invoice', 'in_refund'))
        invoices._aabaan_autofill_analytic(emirate_plan, service_plan)

        for move in invoices:
            for line, missing in move._aabaan_analytic_gaps(
                    emirate_plan, service_plan):
                raise UserError(_(
                    "%(move)s cannot be posted: line \"%(line)s\" has no "
                    "%(missing)s analytic tag.\n\nEvery financial transaction "
                    "must be traceable through the branch (Finance policy "
                    "§7/§20). Set the analytic distribution on the line, "
                    "then post.",
                    move=move.display_name,
                    line=(line.name or line.product_id.display_name or '?'),
                    missing=" and ".join(plan.name for plan in missing)))

    def _post(self, soft=True):
        self._aabaan_check_analytic_segregation()
        return super()._post(soft=soft)
