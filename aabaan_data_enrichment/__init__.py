import logging

from . import models

_logger = logging.getLogger(__name__)


def _post_init_hook(env):
    """Run both sweeps once at install; failures never break the install —
    the server actions can re-run them any time."""
    try:
        _logger.info("Aabaan emirate tagging: %s",
                     env['sale.order'].aabaan_tag_emirates())
        _logger.info("Aabaan contact enrichment: %s",
                     env['res.partner'].aabaan_enrich_contacts())
    except Exception:
        _logger.exception(
            "Aabaan data enrichment sweep failed — run the "
            "'Aabaan: Tag Contract Emirates' / 'Aabaan: Enrich Contacts' "
            "server actions manually.")
