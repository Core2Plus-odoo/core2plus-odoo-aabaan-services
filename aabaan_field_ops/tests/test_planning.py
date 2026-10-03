# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from ast import literal_eval

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPlanningBoard(TransactionCase):

    def test_gantt_view_validates_server_side(self):
        """get_view runs full server-side arch validation — a wrong field
        name in the Gantt fails here instead of in the dispatcher's
        browser."""
        view = self.env.ref('aabaan_field_ops.view_task_gantt_planning')
        arch = self.env['project.task'].get_view(view.id, 'gantt')['arch']
        for needle in ('planned_date_begin', 'date_deadline',
                       'sla_escalated', 'user_ids'):
            self.assertIn(needle, arch)

    def test_planning_board_shows_only_fsm_visits(self):
        action = self.env.ref('aabaan_field_ops.action_planning_board')
        self.assertIn(('project_id.is_fsm', '=', True),
                      literal_eval(action.domain))
        self.assertTrue(action.view_mode.startswith('gantt'))

    def test_to_schedule_catches_undated_open_visits_only(self):
        project = self.env['project.project'].create({
            'name': 'Planning Test FSM', 'is_fsm': True})
        partner = self.env['res.partner'].create({'name': 'Plan Test Co'})
        undated = self.env['project.task'].create({
            'name': 'Undated visit', 'project_id': project.id,
            'partner_id': partner.id})
        dated = self.env['project.task'].create({
            'name': 'Dated visit', 'project_id': project.id,
            'partner_id': partner.id,
            'planned_date_begin': '2026-09-01 08:00:00',
            'date_deadline': '2026-09-01 10:00:00'})
        action = self.env.ref('aabaan_field_ops.action_to_schedule')
        found = self.env['project.task'].search(literal_eval(action.domain))
        self.assertIn(undated, found)
        self.assertNotIn(dated, found,
                         "a visit with a planned date belongs on the "
                         "board, not in the To Schedule backlog")
