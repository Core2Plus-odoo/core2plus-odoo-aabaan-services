# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFieldOps(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        stage_names = ['Scheduled', 'Assigned', 'In Progress',
                       'Follow-up Required', 'Completed', 'Report Issued',
                       'Certificate Issued', 'Cancelled']
        cls.stages = cls.env['project.task.type'].create([
            {'name': name, 'sequence': seq, 'fold': name == 'Cancelled'}
            for seq, name in enumerate(stage_names)])
        cls.project = cls.env['project.project'].create({
            'name': 'Field Ops (test)', 'is_fsm': True,
            'type_ids': [(6, 0, cls.stages.ids)]})
        cls._manual_field('sale.order', 'x_visit_count', 'integer')
        cls._manual_field('sale.order', 'x_followup_days', 'integer')
        cls._manual_field('project.task', 'x_visit_type', 'selection', [
            ('routine', 'Routine'), ('followup', 'Follow-up'),
            ('complaint', 'Complaint')])
        cls._manual_field('project.task', 'x_visit_no', 'integer')
        cls._manual_field('project.task', 'x_sla_due', 'datetime')
        cls.tech = cls.env['res.users'].create({
            'name': 'Tech Ahmed', 'login': 'tech.ahmed@test.aabaan'})
        cls.partner = cls.env['res.partner'].create({'name': 'Ops Test Client'})
        cls.product = cls.env['product.product'].create({
            'name': 'Pest AMC (ops test)', 'type': 'service',
            'service_tracking': 'task_global_project',
            'project_id': cls.project.id})

    @classmethod
    def _manual_field(cls, model_name, name, ttype, selection=None):
        IrModelFields = cls.env['ir.model.fields']
        model = cls.env['ir.model']._get(model_name)
        if IrModelFields.search_count(
                [('model_id', '=', model.id), ('name', '=', name)]):
            return
        vals = {'model_id': model.id, 'name': name, 'ttype': ttype,
                'field_description': name, 'state': 'manual'}
        if selection:
            vals['selection_ids'] = [
                (0, 0, {'value': v, 'name': l, 'sequence': i})
                for i, (v, l) in enumerate(selection)]
        IrModelFields.create(vals)

    def _visit(self, **order_vals):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id,
                                   'product_uom_qty': 2})],
        })
        order.write(dict({'x_visit_count': 2, 'x_followup_days': 3,
                          'visit_technician_id': self.tech.id}, **order_vals))
        order.action_confirm()
        task = self.env['project.task'].search([
            ('sale_order_id', '=', order.id),
            ('x_visit_type', '=', 'routine')], limit=1, order='id')
        return order, task

    @freeze_time('2026-09-01')
    def test_dispatch_and_guarded_flow(self):
        order, visit = self._visit()
        self.assertIn(self.tech, visit.user_ids,
                      "preferred technician must be auto-assigned")

        # start requires an assignee
        visit.with_context(aabaan_visit_guard_bypass=True).write(
            {'user_ids': [(5, 0, 0)]})
        with self.assertRaises(UserError):
            visit.action_start_visit()
        visit.write({'user_ids': [(4, self.tech.id)]})

        # complete requires a start, then a treatment summary
        with self.assertRaises(UserError):
            visit.action_complete_visit()
        visit.action_start_visit()
        self.assertTrue(visit.visit_started_at)
        self.assertEqual(visit.stage_id.name, 'In Progress')
        with self.assertRaises(UserError):
            visit.action_complete_visit()

        # infestation on completion raises the follow-up automatically
        visit.write({'infestation_found': True,
                     'treatment_summary': 'Gel bait applied, kitchen + store'})
        visit.action_complete_visit()
        self.assertTrue(visit.visit_completed_at)
        self.assertTrue(visit.followup_task_id)
        self.assertEqual(visit.followup_task_id.x_visit_type, 'followup')
        self.assertEqual(visit.stage_id.name, 'Follow-up Required')

    @freeze_time('2026-09-01')
    def test_stage_jump_guards(self):
        order, visit = self._visit()
        done = self.stages.filtered(lambda s: s.name == 'Completed')
        cancelled = self.stages.filtered(lambda s: s.name == 'Cancelled')
        with self.assertRaises(UserError, msg="no silent completion"):
            visit.write({'stage_id': done.id})
        with self.assertRaises(UserError, msg="no silent cancellation"):
            visit.write({'stage_id': cancelled.id})
        with self.assertRaises(UserError, msg="cancel needs a reason"):
            visit.action_cancel_visit()
        visit.visit_cancel_reason = 'Customer postponed to next week'
        visit.action_cancel_visit()
        self.assertEqual(visit.stage_id.name, 'Cancelled')
