# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from datetime import date, timedelta

from freezegun import freeze_time

from odoo.tests import TransactionCase, tagged

# The production database defines the x_* fields as manual fields (created via
# ir.model.fields, per the build handoff). A fresh test database does not have
# them, so the setup below recreates them the same way — which also exercises
# the module's runtime field resolution against realistic definitions.
DUBAI_TZ_OFFSET = timedelta(hours=4)


@tagged('post_install', '-at_install')
class TestVisitSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'UAE Mon-Fri (test)',
            'tz': 'Asia/Dubai',
            'attendance_ids': [
                (0, 0, {
                    'name': f'day{day}-{period}',
                    'dayofweek': str(day),
                    'hour_from': hour_from,
                    'hour_to': hour_to,
                    'day_period': period,
                })
                for day in range(5)
                for hour_from, hour_to, period in (
                    (8, 12, 'morning'), (13, 17, 'afternoon'))
            ],
        })
        cls.company.resource_calendar_id = cls.calendar

        stage_names = ['Scheduled', 'Assigned', 'In Progress',
                       'Follow-up Required', 'Completed', 'Report Issued',
                       'Certificate Issued', 'Cancelled']
        cls.stages = cls.env['project.task.type'].create([
            {'name': name, 'sequence': seq}
            for seq, name in enumerate(stage_names)
        ])
        cls.project = cls.env['project.project'].create({
            'name': 'Field Service (test)',
            'is_fsm': True,
            'company_id': cls.company.id,
            'type_ids': [(6, 0, cls.stages.ids)],
        })

        cls._manual_field('sale.order', 'x_visit_count', 'integer')
        cls._manual_field('sale.order', 'x_service_line', 'selection', [
            ('pest', 'Pest Control'), ('tank', 'Water Tank'),
            ('termite', 'Anti-Termite'), ('cleaning', 'Cleaning')])
        cls._manual_field('sale.order', 'x_emirate_regime', 'selection', [
            ('dubai', 'Dubai'), ('sharjah', 'Sharjah'), ('ajman', 'Ajman'),
            ('northern', 'Northern Emirates')])
        cls._manual_field('sale.order', 'x_complaint_sla', 'selection', [
            ('same_day', 'Same day'), ('24h', '24 hours'), ('48h', '48 hours')])
        cls._manual_field('sale.order', 'x_followup_days', 'integer')
        cls._manual_field('sale.order', 'x_site_address', 'char')
        cls._manual_field('project.task', 'x_visit_type', 'selection', [
            ('routine', 'Routine'), ('followup', 'Follow-up'),
            ('complaint', 'Complaint')])
        cls._manual_field('project.task', 'x_visit_no', 'integer')
        cls._manual_field('project.task', 'x_sla_due', 'datetime')
        # Deliberately a char on the task side: exercises the module's
        # tolerance of type drift between the paired manual fields.
        cls._manual_field('project.task', 'x_service_line', 'char')
        cls._manual_field('project.task', 'x_emirate', 'selection', [
            ('dubai', 'Dubai'), ('sharjah', 'Sharjah'), ('ajman', 'Ajman'),
            ('northern', 'Northern Emirates')])

        cls.partner = cls.env['res.partner'].create(
            {'name': 'AAM Properties (test)'})
        cls.product = cls.env['product.product'].create({
            'name': 'Pest Control AMC (test)',
            'type': 'service',
            'list_price': 208.33,
            'service_tracking': 'task_global_project',
            'project_id': cls.project.id,
        })

    @classmethod
    def _manual_field(cls, model_name, name, ttype, selection=None):
        IrModelFields = cls.env['ir.model.fields']
        model = cls.env['ir.model']._get(model_name)
        if IrModelFields.search_count(
                [('model_id', '=', model.id), ('name', '=', name)]):
            return
        vals = {
            'model_id': model.id,
            'name': name,
            'ttype': ttype,
            'field_description': name,
            'state': 'manual',
        }
        if selection:
            vals['selection_ids'] = [
                (0, 0, {'value': value, 'name': label, 'sequence': seq})
                for seq, (value, label) in enumerate(selection)
            ]
        IrModelFields.create(vals)

    def _make_order(self, **values):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': values.get('x_visit_count', 1) or 1,
            })],
        })
        if values:
            order.write(values)
        return order

    def _routine_tasks(self, order):
        return self.env['project.task'].search([
            ('sale_order_id', '=', order.id),
            ('project_id', '=', self.project.id),
            ('x_visit_type', '=', 'routine'),
        ])

    @freeze_time('2026-09-01')
    def test_01_acceptance_12_visit_ajman_contract(self):
        """Handoff acceptance test: a 12-visit Ajman pest contract starting
        1 Sep 2026 produces exactly 12 Scheduled tasks roughly 30 days apart,
        numbered 1-12, none on a non-working day."""
        order = self._make_order(
            x_visit_count=12, x_emirate_regime='ajman', x_service_line='pest',
            x_complaint_sla='24h', x_followup_days=3,
            x_site_address='Site 1, Ajman')
        order.action_confirm()

        tasks = self._routine_tasks(order)
        self.assertEqual(len(tasks), 12,
                         "the task auto-created by service_tracking must be "
                         "absorbed, not duplicated")
        self.assertEqual(sorted(tasks.mapped('x_visit_no')), list(range(1, 13)))
        for task in tasks:
            self.assertTrue(
                task.name.startswith('AAM Properties (test)'),
                "the client name must lead the visit name so it shows first "
                "on the Maintenance Calendar")
            self.assertEqual(task.stage_id.name, 'Scheduled')
            self.assertEqual(task.x_visit_type, 'routine')
            self.assertEqual(task.x_emirate, 'ajman')
            self.assertEqual(task.x_service_line, 'pest')
            local = task.planned_date_begin + DUBAI_TZ_OFFSET
            self.assertLess(local.weekday(), 5,
                            f"visit planned on non-working day {local}")
            self.assertEqual(task.visit_date, task.planned_date_begin.date(),
                             "visit_date must mirror the planned day for the "
                             "date-only Maintenance Calendar")

        begins = sorted(tasks.mapped('planned_date_begin'))
        self.assertEqual((begins[0] + DUBAI_TZ_OFFSET).date(),
                         date(2026, 9, 1))
        for earlier, later in zip(begins, begins[1:]):
            gap = (later - earlier).days
            self.assertTrue(25 <= gap <= 36,
                            f"visits {gap} days apart, expected ~30")

    @freeze_time('2026-09-01')
    def test_02_regeneration_is_idempotent(self):
        order = self._make_order(x_visit_count=12, x_emirate_regime='ajman')
        order.action_confirm()
        before = self._routine_tasks(order)
        order.action_generate_visit_schedule()
        after = self._routine_tasks(order)
        self.assertEqual(set(before.ids), set(after.ids),
                         "re-running generation must not create or delete "
                         "any visit")
        self.assertEqual(sorted(after.mapped('x_visit_no')),
                         list(range(1, 13)))

    @freeze_time('2026-09-01')
    def test_03_midterm_change_never_touches_started_visits(self):
        order = self._make_order(x_visit_count=12, x_emirate_regime='ajman')
        order.action_confirm()
        first = self._routine_tasks(order).filtered(
            lambda t: t.x_visit_no == 1)
        in_progress = self.stages.filtered(lambda s: s.name == 'In Progress')
        first.stage_id = in_progress

        order.x_visit_count = 8
        order.action_generate_visit_schedule()
        tasks = self._routine_tasks(order)
        self.assertEqual(len(tasks), 8)
        self.assertIn(first.id, tasks.ids)
        self.assertEqual(first.stage_id, in_progress,
                         "a started visit must never be re-staged")
        self.assertEqual(first.x_visit_no, 1)
        self.assertEqual(sorted(tasks.mapped('x_visit_no')),
                         list(range(1, 9)))

        order.x_visit_count = 12
        order.action_generate_visit_schedule()
        tasks = self._routine_tasks(order)
        self.assertEqual(len(tasks), 12)
        self.assertIn(first.id, tasks.ids)
        self.assertEqual(first.stage_id, in_progress)

    @freeze_time('2026-09-01')
    def test_04_dubai_fnb_runs_at_two_visits_per_month(self):
        order = self._make_order(
            x_visit_count=12, x_emirate_regime='dubai', is_fnb_premises=True)
        order.action_confirm()
        self.assertEqual(len(self._routine_tasks(order)), 24,
                         "Dubai LO 11 F&B cadence is 2 visits/month "
                         "regardless of x_visit_count")

    @freeze_time('2026-09-01')
    def test_05_followup_and_complaint_visits_are_unbilled_with_sla(self):
        order = self._make_order(
            x_visit_count=2, x_emirate_regime='dubai', x_followup_days=3,
            x_complaint_sla='24h')
        order.action_confirm()

        order.action_create_followup_visit()
        followup = self.env['project.task'].search([
            ('sale_order_id', '=', order.id),
            ('x_visit_type', '=', 'followup')])
        self.assertEqual(len(followup), 1)
        self.assertFalse(followup.sale_line_id,
                         "follow-up visits are never billed under the AMC")
        self.assertEqual((followup.x_sla_due + DUBAI_TZ_OFFSET).date(),
                         date(2026, 9, 4))

        order.action_create_complaint_visit()
        complaint = self.env['project.task'].search([
            ('sale_order_id', '=', order.id),
            ('x_visit_type', '=', 'complaint')])
        self.assertEqual(len(complaint), 1)
        self.assertFalse(complaint.sale_line_id)
        self.assertEqual((complaint.x_sla_due + DUBAI_TZ_OFFSET).date(),
                         date(2026, 9, 2))

        # Regeneration must leave ad-hoc visits alone.
        order.action_generate_visit_schedule()
        self.assertEqual(len(self._routine_tasks(order)), 2)
        self.assertTrue(followup.exists())
        self.assertTrue(complaint.exists())
