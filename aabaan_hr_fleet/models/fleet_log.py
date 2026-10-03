# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo import fields, models


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

    # §16: Vehicle → Driver → Fine → Approval → Recovery. The log itself is
    # native (service type "Traffic Fine"); only the accountability thread is
    # added. Any payroll deduction is applied by the payroll officer via the
    # FINE payslip input, subject to company policy and applicable law.
    fine_employee_id = fields.Many2one(
        'hr.employee', string="Responsible Employee",
        help="Driver accountable for this fine (for recovery follow-up).")
    fine_recovery_state = fields.Selection([
        ('none', 'Not a Recovery'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved for Recovery'),
        ('recovered', 'Recovered'),
        ('waived', 'Waived'),
    ], string="Recovery Status", default='none', tracking=True, copy=False)
