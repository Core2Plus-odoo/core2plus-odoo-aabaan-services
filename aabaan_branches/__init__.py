import logging

from . import models

_logger = logging.getLogger(__name__)

# Facts transcribed from the trade licence documents (uploaded scans):
# Ajman DED professional licence, Dubai DET professional licence,
# Sharjah EDD trading licence. No figure here is invented.
#
# The emirates are operating BRANCHES of the one company, carried on the
# Emirate analytic dimension. Each branch still trades under its own
# licence, so the licence facts hang off the branch, not off a company.
BRANCHES = [
    {
        'head_office': True,
        'hints': ('ajman',),
        'name': 'Ajman',
        'registry': '103074',
        'licence_expiry': '2027-01-08',
        'street': 'Shop 2, Al Nuaimiya 1',
        'city': 'Ajman',
    },
    {
        'hints': ('dubai',),
        'name': 'Dubai',
        'registry': '989256',
        'licence_expiry': '2026-10-13',
        'street': 'Office 126, Bin Salloum Building, Hor Al Anz, Deira',
        'city': 'Dubai',
    },
    {
        'hints': ('sharjah', 'shj'),
        'name': 'Sharjah',
        'registry': '908692',
        'licence_expiry': '2026-07-01',
        'street': 'Shop 1-2, Al Sharq Street, Al Butina',
        'city': 'Sharjah',
    },
]
# The registry number the letterhead used to carry; it appears on none of
# the licence documents, so it is treated as a known-wrong placeholder.
LEGACY_WRONG_REGISTRY = '109374'


def _emirate_plan(env):
    """Resolve the Emirate analytic plan.

    The plan is defined in the production database, not in this repo
    (Rule 2), so it is looked up at runtime and never created here.
    """
    Plan = env['account.analytic.plan'].sudo()
    return Plan.search([('name', 'ilike', 'emirate')], limit=1)


def _setup_branches(env):
    """Carry the licence facts onto the Emirate analytic accounts.

    The emirates are branches of the single company, not separate legal
    entities in Odoo. The accounting dimension that ``aabaan_finance_core``
    already autofills and enforces on every posting *is* the branch, so
    this only annotates those analytic accounts with the licence each
    branch trades under.

    Idempotent: matches by name hint, writes only empty or known-wrong
    values, and never creates or modifies a company.
    """
    plan = _emirate_plan(env)
    if not plan:
        _logger.info(
            "Aabaan branches: no Emirate analytic plan found. Create it in "
            "Accounting > Configuration > Analytic Plans, then upgrade this "
            "module to attach the licence facts.")
        return

    Analytic = env['account.analytic.account'].sudo()
    existing = Analytic.with_context(active_test=False).search(
        [('plan_id', 'child_of', plan.id)])

    for spec in BRANCHES:
        account = next(
            (a for a in existing
             if any(hint in (a.name or '').casefold()
                    for hint in spec['hints'])),
            Analytic.browse())
        if not account:
            try:
                account = Analytic.create({
                    'name': spec['name'],
                    'plan_id': plan.id,
                })
            except Exception:
                # A failure here must not abort the whole module-loading
                # transaction; this is idempotent, so the next upgrade
                # retries the branch.
                _logger.exception(
                    "Aabaan branches: could not create branch %s",
                    spec['name'])
                continue

        vals = {}
        if not account.aabaan_licence_no \
                or account.aabaan_licence_no == LEGACY_WRONG_REGISTRY:
            vals['aabaan_licence_no'] = spec['registry']
        if not account.aabaan_licence_expiry:
            vals['aabaan_licence_expiry'] = spec['licence_expiry']
        if vals:
            try:
                account.write(vals)
            except Exception:
                _logger.exception(
                    "Aabaan branches: could not update branch %s",
                    account.name)


# Odoo demo defaults that must never appear on the public contact page.
PLACEHOLDER_HINTS = ('fake', 'example.com', 'yourcompany', '555-555',
                     'my company')


def _looks_placeholder(value):
    return bool(value) and any(
        hint in value.casefold() for hint in PLACEHOLDER_HINTS)


def _setup_head_office(env):
    """Replace Odoo's demo contact data on the head office with the real
    facts (letterhead / licence documents). Only empty or clearly
    placeholder values are touched."""
    main = env.ref('base.main_company', raise_if_not_found=False)
    if not main:
        return
    head = next((s for s in BRANCHES if s.get('head_office')), None)
    vals = {}
    if not main.phone or _looks_placeholder(main.phone):
        vals['phone'] = '800 22226'
    if not main.email or _looks_placeholder(main.email):
        vals['email'] = 'infoaabanservices@gmail.com'
    if not main.website or _looks_placeholder(main.website):
        vals['website'] = 'https://core2plus-odoo-aabaan.odoo.com'
    if _looks_placeholder(main.street):
        vals['street'] = False
    if _looks_placeholder(main.street2):
        vals['street2'] = False
    if head and (not main.company_registry
                 or main.company_registry == LEGACY_WRONG_REGISTRY):
        vals['company_registry'] = head['registry']
    if head and not main.aabaan_licence_expiry:
        vals['aabaan_licence_expiry'] = head['licence_expiry']
    if vals:
        main.write(vals)
    if not main.vat:
        try:
            main.write({'vat': '104302919600003'})
        except Exception:
            pass  # a VAT validator rejecting the format must not break install


def _post_init_hook(env):
    _setup_head_office(env)
    _setup_branches(env)
