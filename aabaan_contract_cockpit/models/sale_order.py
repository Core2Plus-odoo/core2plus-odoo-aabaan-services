# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import api, fields, models

# The one definition of what counts as a completed stage lives in field
# ops (this module depends on it); a second copy here had already begun
# its inevitable drift.
from odoo.addons.aabaan_field_ops.models.project_task import DONE_HINTS  # noqa: E402,F401


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cockpit_visits_total = fields.Integer(
        string="Visits Planned", compute='_compute_cockpit')
    cockpit_visits_done = fields.Integer(
        string="Visits Completed", compute='_compute_cockpit')
    cockpit_visits_overdue = fields.Integer(
        string="Visits Overdue", compute='_compute_cockpit')
    cockpit_sla_escalations = fields.Integer(
        string="SLA Escalations", compute='_compute_cockpit')
    cockpit_invoiced = fields.Monetary(
        string="Invoiced", compute='_compute_cockpit',
        currency_field='currency_id')
    cockpit_paid = fields.Monetary(
        string="Paid", compute='_compute_cockpit',
        currency_field='currency_id')
    cockpit_outstanding = fields.Monetary(
        string="Outstanding", compute='_compute_cockpit',
        currency_field='currency_id')
    cockpit_days_to_end = fields.Integer(
        string="Days to End of Term", compute='_compute_cockpit',
        help="Negative means the contract is past its end date.")
    cockpit_renewal_state = fields.Selection([
        ('overdue', 'Past end of term'),
        ('window', 'Renewal window (90 days)'),
        ('running', 'Running'),
        ('none', 'No end date'),
    ], string="Renewal", compute='_compute_cockpit')
    cockpit_health = fields.Float(
        string="Health (0-10)", compute='_compute_cockpit', digits=(3, 1))
    cockpit_health_note = fields.Char(
        string="Health Basis", compute='_compute_cockpit')
    cockpit_services = fields.Char(
        string="Services Covered", compute='_compute_cockpit',
        help="All services on this contract, derived dynamically from its "
             "lines — a contract can cover several at once.")
    cockpit_agreement_on_file = fields.Boolean(
        string="Signed Agreement on File", compute='_compute_cockpit',
        help="A document is attached to the contract, or it was signed "
             "online through the portal.")
    cockpit_unscheduled_used = fields.Integer(
        string="Unscheduled Visits Used", compute='_compute_cockpit',
        help="Follow-up and complaint visits — unbilled work.")
    cockpit_unscheduled_over = fields.Integer(
        string="Chargeable Call-outs", compute='_compute_cockpit',
        help="Unscheduled visits beyond the contract's free entitlement "
             "(2 per period outside Dubai, per Article 5).")
    cockpit_entitlement_note = fields.Char(
        string="Call-out Entitlement", compute='_compute_cockpit')

    def _compute_cockpit(self):
        Task = self.env['project.task']
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        has_planned = 'planned_date_begin' in Task._fields

        # unscheduled (unbilled) visit types, resolved once at runtime
        unsched_keys = ()
        if 'x_visit_type' in Task._fields:
            info = Task.fields_get(
                ['x_visit_type'], ['selection']).get('x_visit_type') or {}
            unsched_keys = tuple(
                key for key, label in (info.get('selection') or [])
                if any(hint in f"{key} {label}".casefold()
                       for hint in ('follow', 'complaint')))

        # attachments batched for the whole recordset
        att_counts = {}
        real_ids = [oid for oid in self.ids if oid]
        if real_ids:
            for res_id, count in self.env['ir.attachment']._read_group(
                    [('res_model', '=', 'sale.order'),
                     ('res_id', 'in', real_ids)],
                    ['res_id'], ['__count']):
                att_counts[res_id] = count

        # visits batched too: this compute renders on the Contract Register
        # list (80 rows a page), and one search per row was 80 searches per
        # page load. One search, bucketed by order.
        tasks_by_order = {}
        if real_ids:
            for task in Task.search([
                    ('sale_order_id', 'in', real_ids),
                    ('project_id.is_fsm', '=', True)]):
                tasks_by_order.setdefault(
                    task.sale_order_id.id, []).append(task)

        for order in self:
            # --- delivery, from the generated Field Service visits ---
            total = done = overdue = escalated = unscheduled = 0
            due_count = due_done = 0
            if order.id:
                tasks = tasks_by_order.get(order.id, [])
                total = len(tasks)
                if unsched_keys:
                    unscheduled = sum(
                        1 for task in tasks
                        if task['x_visit_type'] in unsched_keys)
                for task in tasks:
                    stage = (task.stage_id.name or '').casefold()
                    is_done = bool(task.visit_completed_at) or any(
                        hint in stage for hint in DONE_HINTS)
                    if is_done:
                        done += 1
                    if task.sla_escalated:
                        escalated += 1
                    if has_planned and task.planned_date_begin \
                            and task.planned_date_begin < now:
                        due_count += 1
                        if is_done:
                            due_done += 1
                        elif 'cancel' not in stage:
                            overdue += 1
            order.cockpit_visits_total = total
            order.cockpit_visits_done = done
            order.cockpit_visits_overdue = overdue
            order.cockpit_sla_escalations = escalated

            # --- money, from posted customer invoices ---
            invoiced = paid = outstanding = 0.0
            for move in order.invoice_ids.filtered(
                    lambda m: m.state == 'posted'
                    and m.move_type in ('out_invoice', 'out_refund')):
                sign = -1 if move.move_type == 'out_refund' else 1
                invoiced += sign * move.amount_total
                outstanding += sign * move.amount_residual
            paid = invoiced - outstanding
            order.cockpit_invoiced = invoiced
            order.cockpit_paid = paid
            order.cockpit_outstanding = outstanding

            # --- term & renewal ---
            end = order['end_date'] if 'end_date' in order._fields else False
            if end:
                days = (end - today).days
                order.cockpit_days_to_end = days
                order.cockpit_renewal_state = (
                    'overdue' if days < 0 else
                    'window' if days <= 90 else 'running')
            else:
                order.cockpit_days_to_end = 0
                order.cockpit_renewal_state = 'none'

            # --- health: only from signals that actually exist ---
            components = []
            notes = []
            if invoiced > 0:
                ratio = max(0.0, min(1.0, paid / invoiced))
                components.append(ratio)
                notes.append("payment %d%%" % round(ratio * 100))
            if due_count:
                ratio = due_done / due_count
                components.append(ratio)
                notes.append("delivery %d%%" % round(ratio * 100))
            if total:
                ratio = 1.0 - min(1.0, escalated / total)
                components.append(ratio)
                notes.append("SLA %d%%" % round(ratio * 100))
            if components:
                order.cockpit_health = round(
                    10.0 * sum(components) / len(components), 1)
                order.cockpit_health_note = "Based on " + ", ".join(notes)
            else:
                order.cockpit_health = 0.0
                order.cockpit_health_note = "No delivery or billing activity yet"

            # --- agreement & call-out entitlement (multi-service aware) ---
            order.cockpit_services = " + ".join(order.aabaan_service_names())
            signed_online = ('signature' in order._fields
                             and bool(order['signature']))
            order.cockpit_agreement_on_file = bool(
                att_counts.get(order.id)) or signed_online
            order.cockpit_unscheduled_used = unscheduled

            emirate = ''
            if 'x_emirate_regime' in order._fields and order['x_emirate_regime']:
                e_info = order.fields_get(
                    ['x_emirate_regime'], ['selection']).get(
                    'x_emirate_regime') or {}
                emirate = str(dict(e_info.get('selection') or {}).get(
                    order['x_emirate_regime'], order['x_emirate_regime']))
            if 'dubai' in emirate.casefold():
                order.cockpit_unscheduled_over = 0
                order.cockpit_entitlement_note = (
                    "Dubai — unlimited free call-outs (LO 11); %d used"
                    % unscheduled)
            elif emirate:
                over = max(0, unscheduled - 2)
                order.cockpit_unscheduled_over = over
                note = ("%s — 2 free unscheduled visits per period (Art. 5); "
                        "%d used" % (emirate, unscheduled))
                if over:
                    note += ", %d chargeable" % over
                order.cockpit_entitlement_note = note
            else:
                order.cockpit_unscheduled_over = 0
                order.cockpit_entitlement_note = (
                    "Set the contract's emirate to track call-out entitlement")

    def action_view_visits(self):
        """Smart button: this contract's Field Service visits."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Visits — %s" % self.name,
            'res_model': 'project.task',
            'domain': [('sale_order_id', '=', self.id),
                       ('project_id.is_fsm', '=', True)],
            'views': [(False, 'list'), (False, 'form')],
            'context': {'default_sale_order_id': self.id},
        }
