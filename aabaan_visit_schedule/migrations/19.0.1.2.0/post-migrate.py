# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
"""One-time rename of existing open visits to the client-first name format.

The Maintenance Calendar displays the task name, and visits generated before
19.0.1.1.0 read "Visit 3/12 · S00021 · Client". This rewrites every OPEN
(Scheduled/Assigned) contract-linked FSM visit to "Client · Visit 3/12 ·
S00021" so the client shows first on the calendar without re-running the
generator on each contract. Visits at In Progress or beyond are never
renamed; names that don't match the generated pattern are left untouched.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OPEN_STAGE_NAMES = {'scheduled', 'assigned'}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Task = env['project.task']
    if 'sale_order_id' not in Task._fields:
        return
    tasks = Task.search([
        ('project_id.is_fsm', '=', True),
        ('sale_order_id', '!=', False),
    ])
    renamed = 0
    for task in tasks:
        stage = (task.stage_id.name or '').strip().casefold()
        if stage and stage not in OPEN_STAGE_NAMES:
            continue
        partner = task.sale_order_id.partner_id.display_name or ''
        name = task.name or ''
        if not partner or name.startswith(partner):
            continue
        suffix = ' · ' + partner
        core = name[:-len(suffix)] if name.endswith(suffix) else name
        task.name = '%s · %s' % (partner, core)
        renamed += 1
    _logger.info(
        'aabaan_visit_schedule: renamed %s open visits to the client-first '
        'calendar format', renamed)
