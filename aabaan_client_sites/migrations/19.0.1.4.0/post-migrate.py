from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_client_sites import _configure_studio_site_fields


def migrate(cr, version):
    """Apply the sites-only domain to Studio-built site pickers on
    databases where the module is already installed."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _configure_studio_site_fields(env)
