import logging

from . import models

_logger = logging.getLogger(__name__)

# §7 — the finance department's expense categories, seeded as expense
# accounts so nobody creates them inconsistently. Matched by name.
EXPENSE_ACCOUNTS = [
    'Payroll Expenses', 'Fuel', 'Vehicle Maintenance', 'Vehicle Insurance',
    'Accommodation', 'Marketing', 'Municipality Fees', 'License Fees',
    'Commission', 'Chemicals', 'Equipment', 'PPE & Uniforms',
    'Office Expenses', 'Telephone & Internet', 'Utilities',
    'Petty Cash Expenses', 'Repairs & Maintenance', 'Staff Welfare',
    'Other Operational Expenses',
]


def _seed_finance_config(env):
    """§7 expense accounts and §11 cash/petty-cash journals, per active
    company. Idempotent: matched by name (accounts) / type+code (journals);
    a company without a chart of accounts yet is skipped and logged."""
    Journal = env['account.journal'].sudo()
    Account = env['account.account'].sudo()
    for company in env['res.company'].sudo().search([]):
        if not Account.with_company(company).search_count([]):
            _logger.info("Aabaan finance: %s has no chart yet — skipped",
                         company.name)
            continue
        # expense accounts
        existing_codes = set(
            Account.with_company(company).search([]).mapped('code'))
        next_code = 640100
        for name in EXPENSE_ACCOUNTS:
            if Account.with_company(company).search_count(
                    [('name', '=ilike', name)]):
                continue
            while str(next_code) in existing_codes:
                next_code += 10
            try:
                Account.with_company(company).create({
                    'name': name, 'code': str(next_code),
                    'account_type': 'expense',
                })
                existing_codes.add(str(next_code))
            except Exception:
                _logger.exception(
                    "Aabaan finance: could not create account %s for %s",
                    name, company.name)
        # cash + petty cash journals
        for jname, code in (('Cash', 'CSH'), ('Petty Cash', 'PTC')):
            if Journal.search_count([
                    ('company_id', '=', company.id), ('type', '=', 'cash'),
                    '|', ('code', '=', code), ('name', '=ilike', jname)]):
                continue
            try:
                Journal.create({'name': jname, 'code': code,
                                'type': 'cash', 'company_id': company.id})
            except Exception:
                _logger.exception(
                    "Aabaan finance: could not create %s journal for %s",
                    jname, company.name)


def _post_init_hook(env):
    _seed_finance_config(env)
    """§7: expenses run Company → Branch → Department → Category. The Emirate
    and Service Line plans exist from Phase 0; ensure a Department plan exists
    for finance to fill with its departments (data-only, no accounts seeded)."""
    Plan = env['account.analytic.plan']
    if not Plan.search([('name', 'ilike', 'department')], limit=1):
        Plan.create({'name': 'Department'})

    # Standard-first: configure NATIVE analytic applicability so the policy
    # lives where accountants expect it (Accounting > Configuration >
    # Analytic Plans), mirroring the enforcement matrix: Emirate mandatory on
    # invoices and bills, Service Line mandatory on invoices only. The custom
    # _post check remains only for what native cannot do — auto-filling tags
    # from the contract and one clear message — and can be switched off via
    # aabaan_finance_core.enforce_analytic once native applicability alone is
    # preferred. Best-effort: skipped silently if the applicability model
    # differs on this build.
    try:
        Applicability = env['account.analytic.applicability']
        emirate = Plan.search([('name', 'ilike', 'emirate')], limit=1)
        service = Plan.search([('name', 'ilike', 'service')], limit=1)
        wanted = []
        if emirate:
            wanted += [(emirate, 'invoice'), (emirate, 'bill')]
        if service:
            wanted += [(service, 'invoice')]
        domains = dict(Applicability._fields['business_domain'].selection)
        for plan, domain in wanted:
            if domain not in domains:
                continue
            if not Applicability.search([
                    ('analytic_plan_id', '=', plan.id),
                    ('business_domain', '=', domain)], limit=1):
                Applicability.create({
                    'analytic_plan_id': plan.id,
                    'business_domain': domain,
                    'applicability': 'mandatory',
                })
    except Exception:  # noqa: BLE001 — config sugar must never break install
        pass
