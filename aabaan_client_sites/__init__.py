import logging

from . import models

_logger = logging.getLogger(__name__)

# Only the chosen client's own sites may be picked.
SITE_DOMAIN = "[('id', 'child_of', partner_id)]"


def _configure_studio_site_fields(env):
    """Studio-built site pickers (manual many2one fields to res.partner on
    orders/invoices whose label mentions site/premises) get the same
    restriction as the native Site Address — only when they have no domain
    yet, so a deliberate configuration is never overwritten."""
    manual_fields = env['ir.model.fields'].sudo().search([
        ('model', 'in', ('sale.order', 'account.move')),
        ('relation', '=', 'res.partner'),
        ('state', '=', 'manual'),
    ])
    for field in manual_fields:
        label = (field.field_description or '').casefold()
        if any(hint in label for hint in ('site', 'premise')) \
                and not field.domain:
            field.domain = SITE_DOMAIN
            _logger.info(
                "Aabaan client sites: domain set on %s.%s (%s)",
                field.model, field.name, field.field_description)


def _post_init_hook(env):
    _configure_studio_site_fields(env)
