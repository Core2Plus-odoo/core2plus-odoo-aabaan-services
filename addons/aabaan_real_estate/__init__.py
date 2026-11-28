# -*- coding: utf-8 -*-
from . import controllers
from . import models


def _post_init(env):
    """Secret for the lead intake link, so only the portals we give it to can post."""
    import secrets
    ICP = env['ir.config_parameter'].sudo()
    if not ICP.get_param('aabaan_real_estate.lead_token'):
        ICP.set_param('aabaan_real_estate.lead_token', secrets.token_urlsafe(24))
    # Keep the existing (company-wide) CRM stages on the existing teams, so
    # the real-estate pipeline shows only its own stages.
    re_team = env.ref('aabaan_real_estate.crm_team_real_estate', raise_if_not_found=False)
    if re_team:
        others = env['crm.team'].with_context(active_test=False).search([('id', '!=', re_team.id)])
        if others:
            env['crm.stage'].search([('team_ids', '=', False)]).write(
                {'team_ids': [(6, 0, others.ids)]})
