# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    visit_technician_id = fields.Many2one(
        'res.users', string="Preferred Technician",
        domain=[('share', '=', False)],
        help="Auto-assigned to every visit generated for this contract "
             "(routine, follow-up and complaint).")

    def _prepare_visit_task_vals(self, project, stage, visit_no, total, day):
        vals = super()._prepare_visit_task_vals(project, stage, visit_no, total, day)
        if self.visit_technician_id:
            vals['user_ids'] = [(6, 0, [self.visit_technician_id.id])]
        return vals

    def _create_adhoc_visit(self, visit_type):
        action = super()._create_adhoc_visit(visit_type)
        if self.visit_technician_id and action.get('res_id'):
            self.env['project.task'].browse(action['res_id']).write(
                {'user_ids': [(4, self.visit_technician_id.id)]})
        return action
