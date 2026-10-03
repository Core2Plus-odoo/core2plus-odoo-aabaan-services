# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Stage names (compared case-insensitively) in which a visit is still re-plannable.
# Anything else — In Progress and beyond, including Cancelled — is locked:
# regeneration never rewrites, renumbers or deletes it.
OPEN_STAGE_NAMES = {'scheduled', 'assigned'}
AVG_DAYS_PER_MONTH = 30.44
FSM_SERVICE_TRACKING = ('task_global_project', 'task_in_project')


def _field_info(model, fname):
    """Runtime description of a field, or None if the field does not exist.

    The x_* fields of this database are manual (Studio-style) fields created as
    data, not code, so their exact types and selection keys can only be known at
    runtime. Every read/write of them below goes through this introspection so a
    definition drift degrades to a skipped value instead of a crash.
    """
    info = model.fields_get([fname], ['type', 'selection'])
    return info.get(fname)


def _selection_key(model, fname, *needles):
    """Resolve the stored key of a data-defined selection field by substring
    match on its keys and labels (e.g. 'follow' matches 'followup',
    'follow_up' or 'Follow-up')."""
    info = _field_info(model, fname)
    if not info:
        return None
    if info.get('type') != 'selection':
        return needles[0]
    for key, label in info.get('selection') or []:
        haystack = f"{key} {label}".casefold()
        if any(needle in haystack for needle in needles):
            return key
    return None


def _safe_put(model, vals, fname, value):
    """Set vals[fname] only if the field exists and, for selections, the value
    is one of its keys."""
    if value in (None, False):
        return
    info = _field_info(model, fname)
    if not info:
        return
    if info.get('type') == 'selection':
        if value not in [key for key, _label in info.get('selection') or []]:
            return
    vals[fname] = value


# A contract can cover several services at once (e.g. pest control AND
# water tank cleaning). Detection is per order line, first match wins per
# line, so "water tank cleaning" is a tank line, not a cleaning line.
SERVICE_NAMES = [
    ('pest', 'Pest Control'),
    ('tank', 'Water Tank Cleaning'),
    ('termite', 'Anti-Termite Treatment'),
    ('paint', 'Paint Service'),
    ('clean', 'Cleaning Service'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def aabaan_service_names(self):
        """All services this contract covers, in line order, derived
        dynamically from the order lines; falls back to the manual
        x_service_line label when the lines name no known service."""
        self.ensure_one()
        found = []
        for line in self.order_line:
            if line.display_type:
                continue
            text = ' '.join(filter(None, [
                line.name, line.product_id.name])).casefold()
            for needle, label in SERVICE_NAMES:
                if needle in text:
                    if label not in found:
                        found.append(label)
                    break
        if not found:
            fname = 'x_service_line'
            if fname in self._fields and self[fname]:
                info = self.fields_get([fname], ['selection']).get(fname) or {}
                label = dict(info.get('selection') or {}).get(
                    self[fname], self[fname])
                if label:
                    found.append(str(label))
        return found

    is_fnb_premises = fields.Boolean(
        string="F&B Premises (Dubai LO 11)",
        tracking=True,
        help="Food & beverage premises under Dubai Municipality Local Order "
             "No. 11 (2003). When the emirate regime is Dubai, the visit "
             "schedule runs at 2 visits per month, overriding a lower "
             "contracted visit count.",
    )
    visit_task_count = fields.Integer(
        string="Visit Tasks", compute='_compute_visit_task_count')

    def _compute_visit_task_count(self):
        Task = self.env['project.task']
        for order in self:
            origin = order._origin
            order.visit_task_count = (
                Task.search_count(origin._visit_task_domain(all_types=True))
                if origin.id else 0
            )

    # ------------------------------------------------------------------
    # Field access helpers
    # ------------------------------------------------------------------

    def _xval(self, fname, default=None):
        self.ensure_one()
        if fname in self._fields:
            value = self[fname]
            if value:
                return value
        return default

    def _visit_task_domain(self, all_types=False):
        """Tasks of this contract in the Field Service project. Routine-only by
        default (including untyped tasks, so the single task auto-created by
        service_tracking on confirmation is absorbed as visit #1 instead of
        surviving as a duplicate)."""
        self.ensure_one()
        Task = self.env['project.task']
        domain = [('sale_order_id', '=', self.id), ('project_id.is_fsm', '=', True)]
        if not all_types and 'x_visit_type' in Task._fields:
            routine = _selection_key(Task, 'x_visit_type', 'routine')
            domain.append(
                ('x_visit_type', 'in', [routine, False] if routine else [False]))
        return domain

    # ------------------------------------------------------------------
    # Term, count, dates
    # ------------------------------------------------------------------

    def _get_visit_term(self):
        """Contract term as (start, end, notes). Uses the subscription
        start/end dates when set; falls back to the order date and, when no end
        date exists, to a 12-month term — contract frequencies are quoted per
        year ("Yearly 12 Times")."""
        self.ensure_one()
        notes = []
        start = self._xval('start_date') or (self.date_order and self.date_order.date())
        if not start:
            raise UserError(_(
                "%s has no start date (and no order date) to anchor the visit "
                "schedule.") % self.display_name)
        end = self._xval('end_date')
        if not end:
            end = start + relativedelta(years=1, days=-1)
            notes.append(_(
                "No contract end date is set — assumed a 12-month term ending "
                "%s (contract frequencies are quoted per year).")
                % fields.Date.to_string(end))
        if end <= start:
            raise UserError(_(
                "The contract end date must be after the start date on %s.")
                % self.display_name)
        return start, end, notes

    def _get_target_visit_count(self, start, end):
        self.ensure_one()
        notes = []
        count = int(self._xval('x_visit_count', 0) or 0)
        regime = str(self._xval('x_emirate_regime') or '')
        if self.is_fnb_premises and 'dubai' in regime.casefold():
            months = max(1, round(((end - start).days + 1) / AVG_DAYS_PER_MONTH))
            regulatory = 2 * months
            if regulatory > count:
                notes.append(_(
                    "Dubai Local Order No. 11 F&B cadence applied: "
                    "%(regulatory)s visits (2 per month over ~%(months)s "
                    "months) override the contracted count of %(count)s.",
                    regulatory=regulatory, months=months, count=count))
                count = regulatory
        return count, notes

    def _visit_working_day_map(self, start, end):
        """Working weekdays and full-calendar leave days of the company working
        calendar, over [start, end]."""
        self.ensure_one()
        calendar = self.company_id.resource_calendar_id
        weekdays, leave_days = set(), set()
        if calendar:
            weekdays = {int(att.dayofweek) for att in calendar.attendance_ids}
            leaves = self.env['resource.calendar.leaves'].search([
                ('calendar_id', '=', calendar.id),
                ('resource_id', '=', False),
                ('date_from', '<=', datetime.combine(end, time.max)),
                ('date_to', '>=', datetime.combine(start, time.min)),
            ])
            for leave in leaves:
                day = max(leave.date_from.date(), start)
                last = min(leave.date_to.date(), end)
                while day <= last:
                    leave_days.add(day)
                    day += timedelta(days=1)
        if not weekdays:
            weekdays = {0, 1, 2, 3, 4}
        return weekdays, leave_days

    @staticmethod
    def _shift_to_working_day(day, weekdays, leave_days, step=1, limit=60):
        for _unused in range(limit):
            if day.weekday() in weekdays and day not in leave_days:
                return day
            day += timedelta(days=step)
        return day

    def _plan_visit_dates(self, start, end, count, weekdays, leave_days):
        """Evenly spaced planned dates (term days ÷ visit count), each shifted
        forward to a working day (backward at the very end of the term)."""
        term_days = (end - start).days
        min_gap = term_days // count
        dates, previous = [], None
        for index in range(count):
            planned = start + timedelta(days=round(index * term_days / count))
            day = self._shift_to_working_day(planned, weekdays, leave_days)
            if day > end:
                day = self._shift_to_working_day(end, weekdays, leave_days, step=-1)
            if previous and day <= previous and min_gap >= 2:
                bumped = self._shift_to_working_day(
                    previous + timedelta(days=1), weekdays, leave_days)
                if bumped <= end:
                    day = bumped
            dates.append(day)
            previous = day
        return dates

    # ------------------------------------------------------------------
    # FSM project, stages, datetimes
    # ------------------------------------------------------------------

    def _visit_main_sale_line(self):
        self.ensure_one()
        for line in self.order_line:
            product = line.product_id
            if product and product.service_tracking in FSM_SERVICE_TRACKING:
                return line
        return self.env['sale.order.line']

    def _get_fsm_project(self):
        self.ensure_one()
        line = self._visit_main_sale_line()
        if line and line.product_id.project_id:
            return line.product_id.project_id
        project = self.env['project.project'].search([
            ('is_fsm', '=', True),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        if not project:
            raise UserError(_(
                "No Field Service project was found. Configure Field Service "
                "before generating visit schedules."))
        return project

    @api.model
    def _visit_stage(self, project, names):
        for stage in project.type_ids:
            if (stage.name or '').strip().casefold() in names:
                return stage
        return project.type_ids[:1]

    def _visit_tz(self):
        self.ensure_one()
        calendar = self.company_id.resource_calendar_id
        tz_name = (calendar and calendar.tz) or self.company_id.partner_id.tz or 'UTC'
        try:
            return pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            return pytz.utc

    def _visit_datetime(self, day, hour):
        local = self._visit_tz().localize(datetime.combine(day, time(hour=hour)))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _put_when(self, model, vals, fname, day, hour):
        """Write a date-ish value honouring the target field's actual type."""
        field = model._fields.get(fname)
        if field is None:
            return
        if field.type == 'date':
            vals[fname] = day
        elif field.type == 'datetime':
            vals[fname] = self._visit_datetime(day, hour)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _prepare_visit_task_vals(self, project, stage, visit_no, total, day):
        self.ensure_one()
        Task = self.env['project.task']
        vals = {
            # Client name first — the Maintenance Calendar shows the task name,
            # and the customer must be the first thing visible on the event.
            'name': _("%(partner)s · Visit %(no)s/%(total)s · %(order)s",
                      partner=self.partner_id.display_name or '',
                      no=visit_no, total=total, order=self.name),
            'project_id': project.id,
            'partner_id': self.partner_id.id,
        }
        if stage:
            vals['stage_id'] = stage.id
        line = self._visit_main_sale_line()
        if line and 'sale_line_id' in Task._fields:
            vals['sale_line_id'] = line.id
        elif 'sale_order_id' in Task._fields:
            vals['sale_order_id'] = self.id
        self._put_when(Task, vals, 'planned_date_begin', day, 9)
        self._put_when(Task, vals, 'date_deadline', day, 17)
        _safe_put(Task, vals, 'x_visit_type',
                  _selection_key(Task, 'x_visit_type', 'routine'))
        if 'x_visit_no' in Task._fields:
            vals['x_visit_no'] = visit_no
        _safe_put(Task, vals, 'x_service_line', self._xval('x_service_line'))
        _safe_put(Task, vals, 'x_emirate', self._xval('x_emirate_regime'))
        site = self._xval('x_site_address')
        if site:
            vals['description'] = escape(_("Site address: %s") % site)
        return vals

    def action_generate_visit_schedule(self):
        for order in self:
            order._generate_visit_schedule()
        return True

    def _generate_visit_schedule(self):
        """(Re)generate the routine visit schedule of this contract.

        Idempotent: visits at In Progress or beyond keep their stage, dates and
        number; Scheduled/Assigned visits are re-planned in place; missing
        visits are batch-created; surplus open visits are removed.
        """
        self.ensure_one()
        if self.state != 'sale':
            raise UserError(_(
                "Confirm %s before generating its visit schedule.")
                % self.display_name)
        Task = self.env['project.task']
        notes = []
        start, end, term_notes = self._get_visit_term()
        notes += term_notes
        count, count_notes = self._get_target_visit_count(start, end)
        notes += count_notes
        if count <= 0:
            raise UserError(_(
                "Set the contracted visits per term (x_visit_count) on %s "
                "before generating the visit schedule.") % self.display_name)

        project = self._get_fsm_project()
        scheduled_stage = self._visit_stage(project, {'scheduled'})
        weekdays, leave_days = self._visit_working_day_map(start, end)
        dates = self._plan_visit_dates(start, end, count, weekdays, leave_days)

        tasks = Task.search(self._visit_task_domain())
        open_tasks = Task.browse()
        locked_count = 0
        locked_numbers = set()
        has_visit_no = 'x_visit_no' in Task._fields
        for task in tasks:
            stage_name = (task.stage_id.name or '').strip().casefold()
            if not stage_name or stage_name in OPEN_STAGE_NAMES:
                open_tasks |= task
                continue
            locked_count += 1
            # Cancelled visits are kept but their slot is refilled.
            if has_visit_no and 'cancel' not in stage_name:
                number = int(task['x_visit_no'] or 0)
                if 1 <= number <= count:
                    locked_numbers.add(number)

        slots = [n for n in range(1, count + 1) if n not in locked_numbers]

        def sort_key(task):
            when = ''
            if 'planned_date_begin' in Task._fields and task.planned_date_begin:
                when = str(task.planned_date_begin)
            elif 'date_deadline' in Task._fields and task.date_deadline:
                when = str(task.date_deadline)
            return (when, task.id)

        open_sorted = open_tasks.sorted(key=sort_key)
        reused = list(zip(open_sorted, slots))
        for task, number in reused:
            task.write(self._prepare_visit_task_vals(
                project, scheduled_stage, number, count, dates[number - 1]))
        creates = [
            self._prepare_visit_task_vals(
                project, scheduled_stage, number, count, dates[number - 1])
            for number in slots[len(open_sorted):]
        ]
        created = Task.create(creates) if creates else Task.browse()
        surplus = open_sorted[len(slots):]
        removed_count = len(surplus)
        if surplus:
            surplus.unlink()

        summary = {
            'target': count,
            'locked': locked_count,
            'updated': len(reused),
            'created': len(created),
            'removed': removed_count,
        }
        lines = [
            _("Visit schedule generated: %(target)s routine visits from "
              "%(start)s to %(end)s.",
              target=count, start=fields.Date.to_string(start),
              end=fields.Date.to_string(end)),
            _("Kept untouched (In Progress or beyond): %(locked)s · "
              "re-planned: %(updated)s · created: %(created)s · removed "
              "surplus: %(removed)s.", **summary),
            _("Planned dates: %s.")
            % ", ".join(fields.Date.to_string(d) for d in sorted(dates)),
        ]
        lines += notes
        self.message_post(
            body=Markup("<br/>").join(escape(line) for line in lines))
        summary['notes'] = notes
        return summary

    def action_confirm(self):
        res = super().action_confirm()
        if self.env.context.get('skip_aabaan_visit_schedule'):
            return res
        for order in self:
            if order.state != 'sale':
                continue
            has_count = int(order._xval('x_visit_count', 0) or 0) > 0
            dubai_fnb = order.is_fnb_premises and 'dubai' in str(
                order._xval('x_emirate_regime') or '').casefold()
            if not (has_count or dubai_fnb):
                continue
            try:
                order._generate_visit_schedule()
            except UserError as error:
                order.message_post(body=escape(_(
                    "The visit schedule was not generated automatically: %s")
                    % error))
        return res

    # ------------------------------------------------------------------
    # Unbilled follow-up / complaint visits
    # ------------------------------------------------------------------

    def action_create_followup_visit(self):
        self.ensure_one()
        return self._create_adhoc_visit('followup')

    def action_create_complaint_visit(self):
        self.ensure_one()
        return self._create_adhoc_visit('complaint')

    def _complaint_sla_days(self):
        """0 (same day), 1 (24h) or 2 (48h) from the contract's complaint SLA,
        matched on the stored key and its label so the exact selection keys
        remain data-defined."""
        self.ensure_one()
        value = str(self._xval('x_complaint_sla') or '')
        haystack = value
        info = _field_info(self, 'x_complaint_sla')
        if info and info.get('type') == 'selection':
            labels = dict(info.get('selection') or [])
            haystack = f"{value} {labels.get(value, '')}"
        haystack = haystack.casefold()
        if '48' in haystack:
            return 2
        if '24' in haystack:
            return 1
        return 0  # same-day response is the default (Dubai LO 11)

    def _create_adhoc_visit(self, visit_type):
        self.ensure_one()
        Task = self.env['project.task']
        project = self._get_fsm_project()
        stage = self._visit_stage(project, {'scheduled'})
        today = fields.Date.context_today(self)
        weekdays, leave_days = self._visit_working_day_map(
            today, today + timedelta(days=60))
        if visit_type == 'followup':
            label = _("Follow-up")
            needle = 'follow'
            due_day = today + timedelta(
                days=int(self._xval('x_followup_days', 0) or 3))
            planned_day = self._shift_to_working_day(
                due_day, weekdays, leave_days)
        else:
            label = _("Complaint")
            needle = 'complaint'
            due_day = today + timedelta(days=self._complaint_sla_days())
            # Complaint response is due immediately, even on a non-working day.
            planned_day = today
        vals = {
            'name': _("%(partner)s · %(label)s · %(order)s",
                      partner=self.partner_id.display_name or '',
                      label=label, order=self.name),
            'project_id': project.id,
            'partner_id': self.partner_id.id,
        }
        if stage:
            vals['stage_id'] = stage.id
        # Traceability only — deliberately no sale_line_id: follow-up and
        # complaint visits are never billed under the AMC.
        if 'sale_order_id' in Task._fields:
            vals['sale_order_id'] = self.id
        self._put_when(Task, vals, 'planned_date_begin', planned_day, 9)
        self._put_when(Task, vals, 'date_deadline', planned_day, 17)
        self._put_when(Task, vals, 'x_sla_due', due_day, 17)
        _safe_put(Task, vals, 'x_visit_type',
                  _selection_key(Task, 'x_visit_type', needle))
        _safe_put(Task, vals, 'x_service_line', self._xval('x_service_line'))
        _safe_put(Task, vals, 'x_emirate', self._xval('x_emirate_regime'))
        details = [_("%(label)s visit under contract %(order)s — not billed "
                     "under the AMC.", label=label, order=self.name)]
        site = self._xval('x_site_address')
        if site:
            details.append(_("Site address: %s") % site)
        vals['description'] = Markup("<br/>").join(
            escape(detail) for detail in details)
        task = Task.create(vals)
        self.message_post(body=escape(_(
            "%(label)s visit \"%(task)s\" raised — SLA due %(due)s.",
            label=label, task=task.display_name,
            due=fields.Date.to_string(due_day))))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': task.id,
            'view_mode': 'form',
            'name': label,
        }

    def action_view_visit_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Visits"),
            'res_model': 'project.task',
            'view_mode': 'list,form,calendar',
            'domain': self._visit_task_domain(all_types=True),
        }
