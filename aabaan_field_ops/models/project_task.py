# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Stage-name hints, matched case-insensitively — the FSM stages are data on the
# production database (Scheduled → ... → Certificate Issued → Cancelled).
DONE_HINTS = ('complete', 'report issued', 'certificate')
CANCEL_HINT = 'cancel'
PROGRESS_HINT = 'progress'
FOLLOWUP_HINTS = ('follow-up', 'follow up', 'followup')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    visit_started_at = fields.Datetime(
        string="Check-in", readonly=True, copy=False)
    visit_completed_at = fields.Datetime(
        string="Check-out", readonly=True, copy=False)
    visit_duration_actual = fields.Float(
        string="Time on Site (hours)", compute='_compute_visit_duration_actual')
    infestation_found = fields.Boolean(
        string="Infestation Found",
        help="Tick before completing: a follow-up visit (3-day rule, unbilled) "
             "is raised automatically on completion.")
    treatment_summary = fields.Text(
        string="Treatment Carried Out",
        help="Required to complete the visit — areas treated and work done; "
             "feeds the municipality report.")
    chemicals_used = fields.Text(
        string="Chemicals / Materials Used",
        help="Product and quantity, as the municipality return requires.")
    visit_cancel_reason = fields.Text(string="Cancellation Reason", copy=False)
    followup_task_id = fields.Many2one(
        'project.task', string="Follow-up Raised", readonly=True, copy=False)
    sla_escalated = fields.Boolean(copy=False)

    @api.depends('visit_started_at', 'visit_completed_at')
    def _compute_visit_duration_actual(self):
        for task in self:
            if task.visit_started_at and task.visit_completed_at:
                delta = task.visit_completed_at - task.visit_started_at
                task.visit_duration_actual = round(delta.total_seconds() / 3600.0, 2)
            else:
                task.visit_duration_actual = 0.0

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _is_guarded_visit(self):
        """Guardrails apply only to typed Aabaan visits in an FSM project —
        imports, demo data and ordinary project tasks stay untouched."""
        self.ensure_one()
        return bool(
            self.project_id.is_fsm
            and self.sale_order_id
            and 'x_visit_type' in self._fields and self['x_visit_type'])

    def _find_stage(self, *hints):
        self.ensure_one()
        for stage in self.project_id.type_ids:
            name = (stage.name or '').casefold()
            if any(hint in name for hint in hints):
                return stage
        return self.env['project.task.type']

    # ------------------------------------------------------------------
    # guard-railed execution flow
    # ------------------------------------------------------------------

    def action_start_visit(self):
        now = fields.Datetime.now()
        for task in self:
            if task.visit_started_at:
                raise UserError(_(
                    "%s was already started.") % task.display_name)
            if not task.user_ids:
                raise UserError(_(
                    "Assign a technician to \"%s\" before starting the visit.")
                    % task.display_name)
            vals = {'visit_started_at': now}
            stage = task._find_stage(PROGRESS_HINT)
            if stage:
                vals['stage_id'] = stage.id
            task.with_context(aabaan_visit_guard_bypass=True).write(vals)
        return True

    def action_complete_visit(self):
        now = fields.Datetime.now()
        for task in self:
            if not task.visit_started_at:
                raise UserError(_(
                    "Start the visit first — \"%s\" has no check-in.")
                    % task.display_name)
            if task.visit_completed_at:
                raise UserError(_(
                    "%s is already completed.") % task.display_name)
            if not (task.treatment_summary or '').strip():
                raise UserError(_(
                    "Fill in \"Treatment Carried Out\" on the Field Report tab "
                    "before completing — the municipality report needs it."))
            vals = {'visit_completed_at': now}
            note = _("Visit completed — %s on site.") % task.user_ids[:1].name
            if task.infestation_found and not task.followup_task_id:
                order = task.sale_order_id
                if order:
                    action = order._create_adhoc_visit('followup')
                    followup = self.browse(action.get('res_id'))
                    vals['followup_task_id'] = followup.id
                    note = _(
                        "Visit completed with infestation found — follow-up "
                        "\"%s\" raised automatically (3-day rule, unbilled).")\
                        % followup.display_name
                stage = task._find_stage(*FOLLOWUP_HINTS) or task._find_stage(*DONE_HINTS)
            else:
                stage = task._find_stage(*DONE_HINTS)
            if stage:
                vals['stage_id'] = stage.id
            task.with_context(aabaan_visit_guard_bypass=True).write(vals)
            task.message_post(body=note)
        return True

    def action_cancel_visit(self):
        for task in self:
            if not (task.visit_cancel_reason or '').strip():
                raise UserError(_(
                    "Give a cancellation reason on the Field Report tab first "
                    "— cancelled visits must be explainable to the customer."))
            vals = {}
            stage = task._find_stage(CANCEL_HINT)
            if stage:
                vals['stage_id'] = stage.id
            task.with_context(aabaan_visit_guard_bypass=True).write(vals)
            task.message_post(
                body=_("Visit cancelled: %s") % task.visit_cancel_reason)
        return True

    def write(self, vals):
        """Intercept stage jumps that skip the guarded flow (kanban drags,
        mass edits): no silent Completed, In Progress or Cancelled."""
        if 'stage_id' in vals and not self.env.context.get('aabaan_visit_guard_bypass'):
            stage = self.env['project.task.type'].browse(vals['stage_id'])
            name = (stage.name or '').casefold()
            for task in self:
                if not task._is_guarded_visit():
                    continue
                if CANCEL_HINT in name and not (
                        task.visit_cancel_reason or vals.get('visit_cancel_reason')):
                    raise UserError(_(
                        "\"%s\": use the Cancel Visit button — a cancellation "
                        "reason is required.") % task.display_name)
                if any(h in name for h in DONE_HINTS) and not task.visit_completed_at:
                    raise UserError(_(
                        "\"%s\": use the Complete Visit button — it records the "
                        "field report and raises any follow-up automatically.")
                        % task.display_name)
                if PROGRESS_HINT in name and not task.visit_started_at and not vals.get('visit_started_at'):
                    raise UserError(_(
                        "\"%s\": use the Start Visit button — it checks the "
                        "technician in.") % task.display_name)
        return super().write(vals)

    # ------------------------------------------------------------------
    # daily escalation
    # ------------------------------------------------------------------

    @api.model
    def _cron_aabaan_field_escalations(self):
        now = fields.Datetime.now()
        base = [
            ('project_id.is_fsm', '=', True),
            ('stage_id.fold', '=', False),
            ('sla_escalated', '=', False),
        ]
        to_escalate = self.browse()
        if 'x_sla_due' in self._fields:
            to_escalate |= self.search(base + [('x_sla_due', '<', now)])
        if 'planned_date_begin' in self._fields:
            to_escalate |= self.search(base + [
                ('visit_started_at', '=', False),
                ('planned_date_begin', '<', now - timedelta(days=1)),
            ])
        for task in to_escalate:
            user = task.user_ids[:1] or task.project_id.user_id
            task.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Visit overdue / SLA at risk"),
                note=_("This visit is past its SLA deadline or planned date "
                       "and has not been started. Reschedule it or get a "
                       "technician on site."),
                user_id=(user.id if user else self.env.user.id),
            )
            task.sla_escalated = True
