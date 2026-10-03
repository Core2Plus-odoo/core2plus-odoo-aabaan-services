import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Historical no-op.

    This step used to split Dubai and Sharjah into standalone companies
    (`_setup_entities`). From 19.0.3.0.0 the emirates are branches of the
    single company, carried on the Emirate analytic dimension, so that
    function no longer exists and this step must not re-create the
    companies it once made. Kept as a no-op so the version sequence stays
    intact for databases replaying it.
    """
    _logger.info(
        "Aabaan branches 19.0.2.0.0: superseded by the branch model in "
        "19.0.3.0.0 — no entities created.")
