import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Historical no-op.

    This step re-ran the entity split with a hierarchy fix. From
    19.0.3.0.0 the emirates are branches of the single company, so
    `_setup_entities` no longer exists and this step must not re-create
    the companies it once made. Kept as a no-op so the version sequence
    stays intact for databases replaying it.
    """
    _logger.info(
        "Aabaan branches 19.0.2.2.0: superseded by the branch model in "
        "19.0.3.0.0 — no entities created.")
