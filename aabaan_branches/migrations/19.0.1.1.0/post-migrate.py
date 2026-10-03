from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_branches import _setup_branches, _setup_head_office


def migrate(cr, version):
    """Head-office contact fix: replace Odoo demo placeholders (My Company,
    Fake Buena Vista Avenue, +1 555…, example.com) with the real letterhead
    facts, so the public contact page shows genuine details."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _setup_head_office(env)
    _setup_branches(env)
