import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_branches import BRANCHES, _emirate_plan

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move to one company with the emirates as branches.

    Earlier versions split Dubai and Sharjah into standalone companies.
    This step carries their licence facts onto the matching Emirate
    analytic accounts so nothing is lost, then reports what is left for a
    human to decide.

    It deliberately does NOT archive or merge those companies: Odoo cannot
    move journal entries between companies, so consolidating the books is
    an accounting exercise, not a migration. See README.md.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    plan = _emirate_plan(env)
    if not plan:
        _logger.info(
            "Aabaan branches: no Emirate analytic plan — nothing to carry "
            "over; create the plan and upgrade again.")
        return

    Analytic = env['account.analytic.account'].sudo()
    Company = env['res.company'].sudo().with_context(active_test=False)
    main = env.ref('base.main_company', raise_if_not_found=False)
    accounts = Analytic.with_context(active_test=False).search(
        [('plan_id', 'child_of', plan.id)])

    leftover = Company.browse()
    for spec in BRANCHES:
        if spec.get('head_office'):
            continue
        company = next(
            (c for c in Company.search([('id', '!=', main.id if main else 0)])
             if any(hint in f"{c.name} {c.city or ''}".casefold()
                    for hint in spec['hints'])),
            Company.browse())
        if not company:
            continue
        leftover |= company

        branch = next(
            (a for a in accounts
             if any(hint in (a.name or '').casefold()
                    for hint in spec['hints'])),
            Analytic.browse())
        if not branch:
            continue
        vals = {}
        if not branch.aabaan_licence_no and company.company_registry:
            vals['aabaan_licence_no'] = company.company_registry
        if not branch.aabaan_licence_expiry and company.aabaan_licence_expiry:
            vals['aabaan_licence_expiry'] = company.aabaan_licence_expiry
        if vals:
            branch.write(vals)
            _logger.info(
                "Aabaan branches: carried licence facts from company %s to "
                "branch %s", company.name, branch.name)

    if leftover:
        moves = env['account.move'].sudo().search_count(
            [('company_id', 'in', leftover.ids)])
        _logger.warning(
            "Aabaan branches: %s still exist as separate companies, holding "
            "%s journal entr%s between them. The emirates are now branches on "
            "the Emirate analytic dimension, so those books need carrying "
            "into the surviving company by hand -- Odoo cannot move journal "
            "entries between companies, and the effort grows with every "
            "entry posted. Procedure in aabaan_branches/README.md.",
            ", ".join(leftover.mapped('name')),
            moves, "y" if moves == 1 else "ies")
