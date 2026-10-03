# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import date, datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Date-only mirror of the planned start: the Maintenance Calendar (day
    # view) is built on this field, so events render as all-day chips with no
    # clock time and the client name gets the space.
    visit_date = fields.Date(
        string="Visit Date",
        compute='_compute_visit_date', inverse='_inverse_visit_date',
        store=True,
        help="Day of the visit. Rescheduling on the calendar keeps the "
             "standard 09:00–17:00 visit window on the new day.",
    )

    @api.depends('planned_date_begin', 'date_deadline')
    def _compute_visit_date(self):
        for task in self:
            when = task.planned_date_begin or task.date_deadline
            if isinstance(when, datetime):
                when = when.date()
            task.visit_date = when if isinstance(when, date) else False

    def _inverse_visit_date(self):
        for task in self:
            if not task.visit_date:
                continue
            order = task.sale_order_id
            if order:
                begin = order._visit_datetime(task.visit_date, 9)
                end = order._visit_datetime(task.visit_date, 17)
            else:
                # 09:00–17:00 Gulf Standard Time expressed in UTC
                begin = datetime.combine(task.visit_date, time(hour=5))
                end = datetime.combine(task.visit_date, time(hour=13))
            vals = {'planned_date_begin': begin}
            deadline = task._fields.get('date_deadline')
            if deadline is not None:
                vals['date_deadline'] = (
                    task.visit_date if deadline.type == 'date' else end)
            task.write(vals)

    def _aabaan_contract(self):
        self.ensure_one()
        order = self.sale_order_id
        if not order:
            raise UserError(_(
                "%s is not linked to a contract (sale order), so a follow-up "
                "or complaint visit cannot be raised from it.")
                % self.display_name)
        return order

    def action_create_followup_visit(self):
        self.ensure_one()
        return self._aabaan_contract()._create_adhoc_visit('followup')

    def action_create_complaint_visit(self):
        self.ensure_one()
        return self._aabaan_contract()._create_adhoc_visit('complaint')
