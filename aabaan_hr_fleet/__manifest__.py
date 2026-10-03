# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan HR & Fleet',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Finance P5+P6: native HR/Payroll/Attendance/Leave + Fleet, with vehicle-fine payroll recovery',
    'description': """
Finance requirements Priorities 5 and 6, standard-first.

Native (installed as dependencies, configured in the UI):
- Employees, Attendance (check-in/out, overtime), Time Off (annual/sick/
  unpaid leave with approval and balances), Payroll (salary structures,
  allowances, deductions — configure the UAE structure/rules in Payroll).
- Fleet: vehicles, drivers, odometer, fuel, insurance/registration contracts,
  Salik and repairs as service logs with full cost history per vehicle.

Custom (the genuine gap — §16 fine accountability):
- "Traffic Fine" fleet service type and a recovery workflow on fleet service
  logs: employee, recovery state (Pending Approval → Approved → Recovered /
  Waived), tracked in chatter.
- "Vehicle Fine Recovery" payslip Other Input type (code FINE): the payroll
  officer adds the approved amount on the payslip, subject to company policy
  and applicable law (per the requirement's own wording).
Vehicle costs hit the branch P&L through the enforced analytic tags on the
bills that pay for them (aabaan_finance_core).
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['hr', 'hr_attendance', 'hr_holidays', 'hr_payroll', 'fleet'],
    'data': [
        'data/fleet_data.xml',
        'views/fleet_views.xml',
    ],
    'installable': True,
    'application': False,
}
