# -*- coding: utf-8 -*-
"""Data provider for the CEO Dashboard ("Two Businesses, One View").

One call returns the whole month, section by section, in the order of the
client's PDF: cover, 1 AMC vs Cash, 2 AMC Department, 3 Cash Sales,
4 Branch Scorecard, 5 Revenue by Service, 6 Services by Emirate, 7 Credit
Recovery, 8 Sales Team, 9 Expenses & Margin, 10 Cash & Bank.

Rules held throughout:

* Every figure is read from the database; nothing is estimated. Where the
  records needed for a figure do not exist yet (no payments registered, no
  bank statements, no targets set) the figure is zero or blank and the
  screen says so — it is never filled from a model of what it might be.
* Revenue is invoiced revenue excluding VAT, by invoice date, split by the
  stored ``fm_cc_stream`` / ``fm_cc_branch_id`` / ``fm_cc_service``
  classification (see classification.py).
* ``include_draft`` decides whether draft customer invoices and draft
  entries count. Money in the bank is always posted-only: a draft is not
  cash.
* Each figure that maps to records carries ``model`` + ``domain`` so the
  screen can open exactly the records behind it.
"""
from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.fields import Domain

from .classification import SERVICES

try:
    from odoo.addons.fm_asset.models.fm_asset_category import (
        CLIENT_SERVICE_ORDER, SERVICE_LINES)
except ImportError:  # dashboard still works without the FM catalogue
    CLIENT_SERVICE_ORDER, SERVICE_LINES = [], []

SERVICE_LABELS = dict(SERVICES)
BRANCH_ORDER = ['ajman', 'sharjah', 'dubai', 'fujairah']
# Dashboard service key -> the contract's (sale.order.fm_service_line) key,
# where the two vocabularies spell it differently.
DASH_TO_LINE = {'tank': 'water_tank', 'ac': 'hvac'}
LINE_TO_DASH = {v: k for k, v in DASH_TO_LINE.items()}
PAYROLL_WORDS = ('payroll', 'wage', 'salar', 'staff cost', 'gratuity')


def _d(value):
    return fields.Date.to_string(value)


class FmCommandCentre(models.AbstractModel):
    _name = 'fm.command.centre'
    _description = 'CEO Dashboard data provider'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @api.model
    def _pct(self, part, whole, digits=1):
        return round(100.0 * part / whole, digits) if whole else None

    @api.model
    def _delta(self, current, previous):
        if not previous:
            return None
        return round(100.0 * (current - previous) / abs(previous), 1)

    @api.model
    def _month_bounds(self, month):
        today = fields.Date.context_today(self)
        start = today.replace(day=1)
        if month:
            try:
                year, mon = (int(x) for x in str(month).split('-')[:2])
                start = date(year, mon, 1)
            except (TypeError, ValueError):
                pass
        end = start + relativedelta(months=1)
        # "As of" = the last day of the month, or today for the running one.
        as_of = min(end - timedelta(days=1), today)
        if as_of < start:
            as_of = end - timedelta(days=1)
        return start, end, as_of

    @api.model
    def _branches(self):
        branches = self.env['fm.branch'].search(
            [('id', '=', self._br())] if self._br() else [])

        def rank(b):
            emirate = b.emirate or ''
            label = (b.name or '').split(' — ')[-1].casefold()
            for i, key in enumerate(BRANCH_ORDER):
                if key == emirate or key == label:
                    return (i, b.name)
            return (len(BRANCH_ORDER), b.name)
        out = []
        for b in branches.sorted(rank):
            out.append({
                'id': b.id,
                'name': (b.name or '').split(' — ')[-1],
                'manager': b.manager_id.name or '',
                'amc_target': b.amc_monthly_target or 0.0,
                'cash_target': b.cash_monthly_target or 0.0,
            })
        return out

    @api.model
    def _states(self, include_draft):
        return ('draft', 'posted') if include_draft else ('posted',)

    # ---- service filter (context key fm_cc_service) -------------------

    @api.model
    def _svc(self):
        return self.env.context.get('fm_cc_service') or False

    @api.model
    def _br(self):
        return self.env.context.get('fm_cc_branch') or False

    @api.model
    def _svc_line_key(self):
        svc = self._svc()
        return DASH_TO_LINE.get(svc, svc) if svc else False

    @api.model
    def _service_options(self):
        """The service filter: the client's catalogue (same order and names
        as the Maintenance Calendar), then any other dashboard service that
        actually carries invoices (lab tests, projects, ...)."""
        line_labels = dict(SERVICE_LINES)
        keys = [LINE_TO_DASH.get(k, k) for k in CLIENT_SERVICE_ORDER]
        keys = [k for k in keys if k in SERVICE_LABELS]
        used = {v for (v,) in self.env['account.move']._read_group(
            [('fm_cc_service', '!=', False)], ['fm_cc_service'], [])}
        keys += [k for k, _l in SERVICES if k not in keys and k in used]
        return [{'key': k, 'label': line_labels.get(DASH_TO_LINE.get(k, k))
                 or SERVICE_LABELS[k]} for k in keys]

    @api.model
    def _inv_domain(self, states, start=None, end=None, types=('out_invoice', 'out_refund')):
        domain = [('move_type', 'in', list(types)), ('state', 'in', list(states))]
        if self._svc():
            domain.append(('fm_cc_service', '=', self._svc()))
        if self._br():
            domain.append(('fm_cc_branch_id', '=', self._br()))
        if start:
            domain.append(('invoice_date', '>=', _d(start)))
        if end:
            domain.append(('invoice_date', '<', _d(end)))
        return domain

    @api.model
    def _contracts(self):
        Sale = self.env['sale.order']
        domain = [('state', '=', 'sale')]
        if 'is_fm_contract' in Sale._fields:
            domain.append(('is_fm_contract', '=', True))
        if self._svc() and 'fm_service_line' in Sale._fields:
            domain.append(('fm_service_line', '=', self._svc_line_key()))
        if self._br():
            domain.append(('fm_cc_branch_id', '=', self._br()))
        out = []
        for o in Sale.search(domain):
            start = (o['fm_start_date'] if 'fm_start_date' in o._fields else False) \
                or (o['start_date'] if 'start_date' in o._fields else False) \
                or (o.date_order and o.date_order.date())
            end = (o['fm_end_date'] if 'fm_end_date' in o._fields else False) \
                or (o['end_date'] if 'end_date' in o._fields else False)
            out.append({
                'id': o.id, 'start': start, 'end': end,
                'amount': o.amount_untaxed,
                'partner': o.partner_id.commercial_partner_id.id,
                'branch': o.fm_cc_branch_id.id,
                'user': o.user_id,
            })
        # renewal = the customer already had a contract that started earlier
        first = {}
        for c in sorted(out, key=lambda c: (c['start'] or date.min, c['id'])):
            c['renewal'] = c['partner'] in first
            first.setdefault(c['partner'], c['id'])
        return out

    @api.model
    def _fsm_domain(self):
        Task = self.env['project.task']
        domain = []
        if 'is_fsm' in self.env['project.project']._fields:
            domain.append(('project_id.is_fsm', '=', True))
        if 'fm_contract_order_id' in Task._fields:
            domain += ['|', ('fm_contract_order_id', '!=', False),
                       ('sale_order_id', '!=', False)]
        else:
            domain.append(('sale_order_id', '!=', False))
        if self._br():
            domain.append(('fm_cc_branch_id', '=', self._br()))
        key = self._svc_line_key()
        if key and 'fm_service_line' in self.env['sale.order']._fields:
            links = [l for l in ('fm_contract_order_id', 'sale_order_id') if l in Task._fields]
            clauses = [[('fm_service_line', '=', key)]] + [
                [('fm_service_line', '=', False), ('%s.fm_service_line' % l, '=', key)]
                for l in links]
            domain = list(Domain.AND([domain, Domain.OR(clauses)]))
        return domain

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    @api.model
    def get_data(self, month=False, include_draft=True, variant='full', service=False,
                 branch=False):
        options = self._service_options()
        if service not in [o['key'] for o in options]:
            service = False
        branch_options = [{'id': b['id'], 'name': b['name']} for b in self._branches()]
        if branch not in [b['id'] for b in branch_options]:
            branch = False
        provider = self.with_context(fm_cc_service=service or False,
                                     fm_cc_branch=branch or False)
        data = provider._get_data(month, include_draft, variant)
        data['branch'] = branch
        data['branch_label'] = next(
            (b['name'] for b in branch_options if b['id'] == branch), '')
        data['branch_options'] = branch_options
        data['service'] = service
        data['service_label'] = next(
            (o['label'] for o in options if o['key'] == service), '')
        data['service_options'] = options
        return data

    @api.model
    def _get_data(self, month=False, include_draft=True, variant='full'):
        include_draft = bool(include_draft)
        start, end, as_of = self._month_bounds(month)
        prev_start = start - relativedelta(months=1)
        states = self._states(include_draft)
        company = self.env.company
        branches = self._branches()
        ctx = {
            'start': start, 'end': end, 'as_of': as_of,
            'prev_start': prev_start, 'states': states,
            'branches': branches,
            'include_draft': include_draft,
        }

        revenue = self._revenue(ctx)
        amc = self._amc(ctx, revenue)
        cash = self._cash(ctx, revenue)
        credit = self._credit(ctx)
        clients = self._new_clients(ctx)
        scorecard = self._scorecard(ctx, revenue, credit, clients)
        services = self._services(ctx) if variant != 'compact' else {
            'rows': [], 'columns': [], 'grand': 0.0, 'max': 1, 'notes': {}}
        sales = self._sales_team(ctx)
        expenses = self._expenses(ctx, revenue)
        bank = self._bank(ctx)

        target = sum(b['amc_target'] + b['cash_target'] for b in branches)
        total = revenue['amc'] + revenue['cash']
        team = 0
        if 'hr.employee' in self.env:
            emp_dom = [('company_id', 'in', self.env.companies.ids)]
            emp_branch = next((f for f in ('fm_branch_id', 'branch_id')
                               if f in self.env['hr.employee']._fields), None)
            if self._br() and emp_branch:
                emp_dom.append((emp_branch, '=', self._br()))
            team = self.env['hr.employee'].search_count(emp_dom)
        draft_count = self.env['account.move'].search_count(
            self._inv_domain(('draft',), start, end))

        cover = {
            'total': total,
            'amc': revenue['amc'], 'cash': revenue['cash'],
            'amc_share': self._pct(revenue['amc'], total, 0),
            'cash_share': self._pct(revenue['cash'], total, 0),
            'target': target,
            'achieved': self._pct(total, target),
            'jobs': amc['visits_done'] + cash['jobs'],
            'amc_visits': amc['visits_done'],
            'cash_jobs': cash['jobs'],
            'new_clients': clients['count'],
            'new_clients_delta': self._delta(clients['count'], clients['prev_count']),
            'receivables': credit['total'],
            'overdue': credit['overdue'],
            'margin': expenses['margin'],
            'profit': expenses['profit'],
            'drill_revenue': {'model': 'account.move', 'domain': revenue['domain'],
                              'name': 'Invoices this month'},
        }

        return {
            'company': company.name,
            'company_id': company.id,
            'tagline': company.fm_cc_tagline or '',
            'currency': company.currency_id.name or 'AED',
            'month': start.strftime('%Y-%m'),
            'month_label': start.strftime('%B %Y'),
            'prev_month_label': prev_start.strftime('%B'),
            'as_of': as_of.strftime('%d %b %Y'),
            'generated': fields.Datetime.context_timestamp(
                self, fields.Datetime.now()).strftime('%d %b %Y, %H:%M'),
            'include_draft': include_draft,
            'draft_count': draft_count,
            'branch_count': len(branches),
            'team': team,
            'cover': cover,
            'versus': self._versus(ctx, revenue, amc, cash, credit),
            'amc': amc,
            'cash': cash,
            'scorecard': scorecard,
            'services': services,
            'credit': credit,
            'sales': sales,
            'expenses': expenses,
            'bank': bank,
        }

    # ------------------------------------------------------------------
    # revenue (shared by most sections)
    # ------------------------------------------------------------------

    def _revenue(self, ctx):
        Move = self.env['account.move']
        domain = self._inv_domain(ctx['states'], ctx['start'], ctx['end'])
        by_branch = defaultdict(lambda: {'amc': 0.0, 'cash': 0.0,
                                         'amc_jobs': 0, 'cash_jobs': 0})
        totals = {'amc': 0.0, 'cash': 0.0, 'amc_jobs': 0, 'cash_jobs': 0}
        for branch, stream, mtype, amount, count in Move._read_group(
                domain, ['fm_cc_branch_id', 'fm_cc_stream', 'move_type'],
                ['amount_untaxed_signed:sum', '__count']):
            stream = stream or 'cash'
            row = by_branch[branch.id or False]
            row[stream] += amount or 0.0
            totals[stream] += amount or 0.0
            if mtype == 'out_invoice':
                row[stream + '_jobs'] += count
                totals[stream + '_jobs'] += count

        # 12 months ending with the selected one
        m12_start = ctx['start'] - relativedelta(months=11)
        months = []
        index = {}
        for i in range(12):
            m = m12_start + relativedelta(months=i)
            index[(m.year, m.month)] = len(months)
            months.append({'key': m.strftime('%Y-%m'), 'label': m.strftime('%b'),
                           'amc': 0.0, 'cash': 0.0})
        for mon, stream, amount in Move._read_group(
                self._inv_domain(ctx['states'], m12_start, ctx['end']),
                ['invoice_date:month', 'fm_cc_stream'],
                ['amount_untaxed_signed:sum']):
            if not mon:
                continue
            pos = index.get((mon.year, mon.month))
            if pos is not None:
                months[pos][stream or 'cash'] += amount or 0.0

        return dict(totals, by_branch=by_branch, months=months, domain=domain)

    # ------------------------------------------------------------------
    # 1 · AMC vs Cash
    # ------------------------------------------------------------------

    def _versus(self, ctx, revenue, amc, cash, credit):
        months = revenue['months']
        notes = []
        amc_vals = [m['amc'] for m in months]
        cash_vals = [m['cash'] for m in months]
        if any(amc_vals):
            first = next((v for v in amc_vals if v), 0)
            notes.append(('AMC', 'moved from %s to %s over the 12 months'
                          % (self._k(first), self._k(amc_vals[-1]))))
        if any(cash_vals):
            hi = max(range(12), key=lambda i: cash_vals[i])
            lo = min((i for i in range(12) if cash_vals[i]),
                     key=lambda i: cash_vals[i], default=hi)
            notes.append(('Cash sales', 'peaked at %s in %s; lowest %s in %s'
                          % (self._k(cash_vals[hi]), months[hi]['label'],
                             self._k(cash_vals[lo]), months[lo]['label'])))
        total = revenue['amc'] + revenue['cash']
        amc_target = sum(b['amc_target'] for b in ctx['branches'])
        cash_target = sum(b['cash_target'] for b in ctx['branches'])
        return {
            'amc': {
                'revenue': revenue['amc'],
                'share': self._pct(revenue['amc'], total, 0),
                'target': amc_target,
                'achieved': self._pct(revenue['amc'], amc_target, 0),
                'visits_done': amc['visits_done'],
                'visits_planned': amc['visits_planned'],
                'per_visit': (revenue['amc'] / amc['visits_done'])
                if amc['visits_done'] else None,
                'receivable': credit['amc'],
            },
            'cash': {
                'revenue': revenue['cash'],
                'share': self._pct(revenue['cash'], total, 0),
                'target': cash_target,
                'achieved': self._pct(revenue['cash'], cash_target, 0),
                'jobs': cash['jobs'],
                'avg_job': cash['avg_job'],
                'receivable': credit['cash'],
            },
            'months': months,
            'notes': notes,
        }

    @api.model
    def _k(self, value):
        value = value or 0.0
        if abs(value) >= 1e6:
            return 'AED %.2fM' % (value / 1e6)
        if abs(value) >= 1e3:
            return 'AED %.1fK' % (value / 1e3)
        return 'AED %d' % round(value)

    # ------------------------------------------------------------------
    # 2 · AMC Department
    # ------------------------------------------------------------------

    def _amc(self, ctx, revenue):
        start, end, as_of = ctx['start'], ctx['end'], ctx['as_of']
        contracts = self._contracts()
        in60 = as_of + timedelta(days=60)

        def active(c):
            return (c['start'] and c['start'] <= as_of
                    and (not c['end'] or c['end'] >= as_of))

        def started(c, s, e):
            return c['start'] and s <= c['start'] < e

        new = [c for c in contracts if started(c, start, end) and not c['renewal']]
        ren = [c for c in contracts if started(c, start, end) and c['renewal']]
        due = [c for c in contracts if c['end'] and as_of <= c['end'] <= in60]
        act = [c for c in contracts if active(c)]

        # monthly new vs renewals
        chart = []
        m12 = start - relativedelta(months=11)
        for i in range(12):
            s = m12 + relativedelta(months=i)
            e = s + relativedelta(months=1)
            chart.append({
                'label': s.strftime('%b'),
                'new': sum(1 for c in contracts if started(c, s, e) and not c['renewal']),
                'renewal': sum(1 for c in contracts if started(c, s, e) and c['renewal']),
            })

        # visits
        Task = self.env['project.task']
        fsm = self._fsm_domain()
        visit_domain = fsm + [
            ('planned_date_begin', '>=', fields.Datetime.to_string(start)),
            ('planned_date_begin', '<', fields.Datetime.to_string(end))]
        done_ext = ['|', ('state', '=', '1_done'), ('stage_id.fold', '=', True)]
        planned_by_branch = defaultdict(int)
        done_by_branch = defaultdict(int)
        if 'planned_date_begin' in Task._fields:
            for branch, count in Task._read_group(
                    visit_domain, ['fm_cc_branch_id'], ['__count']):
                planned_by_branch[branch.id or False] += count
            for branch, count in Task._read_group(
                    visit_domain + done_ext, ['fm_cc_branch_id'], ['__count']):
                done_by_branch[branch.id or False] += count

        # receivables (AMC) by branch
        rec = self._receivable_by(ctx, 'amc')

        rows = []
        branch_ids = [b['id'] for b in ctx['branches']]
        extra = [False] if (
            revenue['by_branch'].get(False, {}).get('amc')
            or any(c['branch'] is False for c in act)
            or planned_by_branch.get(False) or rec.get(False)) else []
        sale_dom = [('state', '=', 'sale')]
        if 'is_fm_contract' in self.env['sale.order']._fields:
            sale_dom.append(('is_fm_contract', '=', True))
        if self._svc() and 'fm_service_line' in self.env['sale.order']._fields:
            sale_dom.append(('fm_service_line', '=', self._svc_line_key()))
        if self._br():
            sale_dom.append(('fm_cc_branch_id', '=', self._br()))
        for bid in branch_ids + extra:
            b = next((x for x in ctx['branches'] if x['id'] == bid), None)
            amount = revenue['by_branch'].get(bid, {}).get('amc', 0.0)
            target = b['amc_target'] if b else 0.0
            rows.append({
                'id': bid,
                'name': b['name'] if b else 'Unassigned',
                'revenue': amount,
                'target': target,
                'achieved': self._pct(amount, target, 0),
                'active': sum(1 for c in act if c['branch'] == bid),
                'visits_done': done_by_branch.get(bid, 0),
                'visits_planned': planned_by_branch.get(bid, 0),
                'due60': sum(1 for c in due if c['branch'] == bid),
                'receivable': rec.get(bid, 0.0),
                'drill': {'model': 'sale.order',
                          'domain': sale_dom + [('fm_cc_branch_id', '=', bid)],
                          'name': 'AMC contracts — %s' % (b['name'] if b else 'Unassigned')},
            })
        totals = {
            'revenue': sum(r['revenue'] for r in rows),
            'target': sum(r['target'] for r in rows),
            'active': len(act),
            'visits_done': sum(r['visits_done'] for r in rows),
            'visits_planned': sum(r['visits_planned'] for r in rows),
            'due60': len(due),
            'receivable': sum(r['receivable'] for r in rows),
        }
        totals['achieved'] = self._pct(totals['revenue'], totals['target'], 0)

        note = None
        if due:
            top = max(rows, key=lambda r: r['due60'])
            note = {'count': len(due), 'branch': top['name'], 'branch_count': top['due60']}

        ids = lambda items: [c['id'] for c in items]
        return {
            'active': len(act), 'new': len(new), 'renewals': len(ren),
            'due60': len(due), 'due60_value': sum(c['amount'] for c in due),
            # contract value (sale order, excl. VAT) behind each count
            'active_value': sum(c['amount'] for c in act),
            'new_value': sum(c['amount'] for c in new),
            'renewals_value': sum(c['amount'] for c in ren),
            'visits_done': totals['visits_done'],
            'visits_planned': totals['visits_planned'],
            'chart': chart, 'rows': rows, 'totals': totals, 'note': note,
            'drill_active': {'model': 'sale.order', 'domain': [('id', 'in', ids(act))],
                             'name': 'Active AMC contracts'},
            'drill_new': {'model': 'sale.order', 'domain': [('id', 'in', ids(new))],
                          'name': 'New AMC contracts'},
            'drill_renewals': {'model': 'sale.order', 'domain': [('id', 'in', ids(ren))],
                               'name': 'AMC renewals'},
            'drill_due': {'model': 'sale.order', 'domain': [('id', 'in', ids(due))],
                          'name': 'Contracts due in 60 days'},
            'drill_visits': {'model': 'project.task', 'domain': visit_domain,
                             'name': 'AMC visits this month'},
        }

    # ------------------------------------------------------------------
    # 3 · Cash Sales
    # ------------------------------------------------------------------

    def _cash(self, ctx, revenue):
        start, end = ctx['start'], ctx['end']
        jobs = revenue['cash_jobs']
        cash_dom = self._inv_domain(ctx['states'], start, end, ('out_invoice',)) + [
            ('fm_cc_stream', '=', 'cash')]
        rec = self._receivable_by(ctx, 'cash')

        rows = []
        branch_ids = [b['id'] for b in ctx['branches']]
        extra = [False] if (revenue['by_branch'].get(False, {}).get('cash')
                            or rec.get(False)) else []
        for bid in branch_ids + extra:
            b = next((x for x in ctx['branches'] if x['id'] == bid), None)
            data = revenue['by_branch'].get(bid, {})
            amount = data.get('cash', 0.0)
            n = data.get('cash_jobs', 0)
            target = b['cash_target'] if b else 0.0
            rows.append({
                'id': bid, 'name': b['name'] if b else 'Unassigned',
                'revenue': amount, 'target': target,
                'achieved': self._pct(amount, target, 0),
                'jobs': n, 'avg_job': amount / n if n else None,
                'unpaid': rec.get(bid, 0.0),
                'drill': {'model': 'account.move',
                          'domain': cash_dom + [('fm_cc_branch_id', '=', bid)],
                          'name': 'Cash sales — %s' % (b['name'] if b else 'Unassigned')},
            })
        totals = {
            'revenue': sum(r['revenue'] for r in rows),
            'target': sum(r['target'] for r in rows),
            'jobs': sum(r['jobs'] for r in rows),
            'unpaid': sum(r['unpaid'] for r in rows),
        }
        totals['achieved'] = self._pct(totals['revenue'], totals['target'], 0)
        totals['avg_job'] = totals['revenue'] / totals['jobs'] if totals['jobs'] else None

        # payments received against cash-sale invoices this month
        Payment = self.env['account.payment']
        pay_domain = [('payment_type', '=', 'inbound'),
                      ('state', 'in', ('in_process', 'paid', 'posted')),
                      ('date', '>=', _d(start)), ('date', '<', _d(end))]
        modes = {'cash': 0.0, 'card': 0.0, 'bank': 0.0}
        mode_ids = {'cash': [], 'card': [], 'bank': []}
        same_day = set()
        paid_jobs = set()
        pay_ids = []
        for pay in Payment.search(pay_domain):
            invoices = pay.reconciled_invoice_ids if 'reconciled_invoice_ids' in pay._fields \
                else self.env['account.move']
            if 'invoice_ids' in pay._fields:
                invoices |= pay.invoice_ids
            cash_inv = invoices.filtered(lambda m: m.fm_cc_stream == 'cash')
            if not cash_inv:
                continue
            pay_ids.append(pay.id)
            label = ' '.join(filter(None, [
                pay.journal_id.name or '',
                pay.payment_method_line_id.name or '' if 'payment_method_line_id' in pay._fields else '',
            ])).casefold()
            if 'card' in label or 'pos' in label.split():
                mode = 'card'
            elif pay.journal_id.type == 'cash':
                mode = 'cash'
            else:
                mode = 'bank'
            modes[mode] += pay.amount
            mode_ids[mode].append(pay.id)
            for inv in cash_inv:
                paid_jobs.add(inv.id)
                if inv.invoice_date and inv.invoice_date == pay.date:
                    same_day.add(inv.id)
        mode_total = sum(modes.values())
        payment_modes = [
            {'key': key, 'label': label, 'amount': modes[key],
             'share': self._pct(modes[key], mode_total, 0),
             'drill': {'model': 'account.payment',
                       'domain': [('id', 'in', mode_ids[key])],
                       'name': label} if mode_ids[key] else None}
            for key, label in (('cash', 'Cash'), ('card', 'Card'),
                               ('bank', 'Bank transfer'))]

        # cash-journal statements: the daily cash match
        Statement = self.env['account.bank.statement']
        statements = Statement.search([
            ('journal_id.type', '=', 'cash'),
            ('date', '>=', _d(start)), ('date', '<', _d(end))])
        days = set()
        bad_days = set()
        differences = []
        for st in statements:
            diff = (st.balance_end_real or 0.0) - (st.balance_end or 0.0)
            days.add(st.date)
            if abs(diff) >= 0.01:
                bad_days.add(st.date)
                differences.append({
                    'amount': abs(diff), 'journal': st.journal_id.name,
                    'date': st.date.strftime('%d %b') if st.date else ''})
        month_jobs_ids = self.env['account.move'].search(cash_dom).ids
        with_payment = self.env['account.move'].search_count(
            [('id', 'in', month_jobs_ids),
             ('payment_state', 'in', ('paid', 'in_payment', 'partial'))])

        return {
            'jobs': jobs,
            'revenue': revenue['cash'],
            'avg_job': revenue['cash'] / jobs if jobs else None,
            'same_day': len(same_day),
            'same_day_pct': self._pct(len(same_day), jobs, 0),
            'payment_modes': payment_modes,
            'payment_total': mode_total,
            'rows': rows, 'totals': totals,
            'checks': {
                'receipts': with_payment, 'jobs': jobs,
                'days_matched': len(days - bad_days), 'days': len(days),
                'differences': differences[:3],
                'difference_count': len(differences),
            },
            'drill_jobs': {'model': 'account.move', 'domain': cash_dom,
                           'name': 'Cash sale jobs this month'},
            'drill_payments': {'model': 'account.payment',
                               'domain': [('id', 'in', pay_ids)],
                               'name': 'Cash sale payments this month'},
        }

    # ------------------------------------------------------------------
    # receivables
    # ------------------------------------------------------------------

    def _open_domain(self, ctx):
        domain = [('move_type', '=', 'out_invoice'),
                  ('state', 'in', list(ctx['states'])),
                  ('invoice_date', '<=', _d(ctx['as_of'])),
                  ('amount_residual', '>', 0)]
        if self._svc():
            domain.append(('fm_cc_service', '=', self._svc()))
        if self._br():
            domain.append(('fm_cc_branch_id', '=', self._br()))
        return domain

    def _receivable_by(self, ctx, stream):
        out = defaultdict(float)
        for branch, amount in self.env['account.move']._read_group(
                self._open_domain(ctx) + [('fm_cc_stream', '=', stream)],
                ['fm_cc_branch_id'], ['amount_residual:sum']):
            out[branch.id or False] += amount or 0.0
        return out

    def _credit(self, ctx):
        # Aged from the invoice date ("how old the debt is", Accounts SOP):
        # draft invoices recompute their due date, so it cannot be trusted.
        Move = self.env['account.move']
        as_of = ctx['as_of']
        open_dom = self._open_domain(ctx)
        total = amc = cash = 0.0
        for stream, amount in Move._read_group(
                open_dom, ['fm_cc_stream'], ['amount_residual:sum']):
            total += amount or 0.0
            if stream == 'amc':
                amc += amount or 0.0
            else:
                cash += amount or 0.0

        def cut(days):
            return _d(as_of - timedelta(days=days))
        buckets = [
            ('b30', '0–30 days', 'Normal', [('invoice_date', '>=', cut(30))]),
            ('b60', '31–60 days', 'Follow up', [('invoice_date', '<', cut(30)),
                                                ('invoice_date', '>=', cut(60))]),
            ('b90', '61–90 days', 'Cash only', [('invoice_date', '<', cut(60)),
                                                ('invoice_date', '>=', cut(90))]),
            ('b90p', '90+ days', 'CEO action', [('invoice_date', '<', cut(90))]),
        ]
        aging = []
        for key, label, action, extra in buckets:
            domain = open_dom + extra
            amount = Move._read_group(domain, [], ['amount_residual:sum'])[0][0] or 0.0
            aging.append({'key': key, 'label': label, 'action': action,
                          'amount': amount,
                          'drill': {'model': 'account.move', 'domain': domain,
                                    'name': 'Receivables %s' % label}})
        overdue = aging[2]['amount'] + aging[3]['amount']
        overdue_domain = open_dom + [('invoice_date', '<', cut(60))]

        # key B2B accounts: the biggest customers billed this month
        month_dom = self._inv_domain(ctx['states'], ctx['start'], ctx['end'], ('out_invoice',))
        rows = Move._read_group(month_dom, ['commercial_partner_id'],
                                ['amount_untaxed_signed:sum'])
        rows.sort(key=lambda r: -(r[1] or 0.0))
        companies = [r for r in rows if r[0].is_company] or rows
        accounts = []
        Line = self.env['account.move.line']
        for partner, amount in companies[:5]:
            pdom = month_dom + [('commercial_partner_id', '=', partner.id)]
            streams = Move._read_group(pdom, ['fm_cc_stream'], ['amount_untaxed_signed:sum'])
            stream = max(streams, key=lambda r: r[1] or 0.0)[0] if streams else 'cash'
            svc = Line._read_group(
                [('move_id', 'in', Move.search(pdom).ids), ('display_type', '=', 'product')],
                ['fm_cc_service'], ['balance:sum'])
            svc.sort(key=lambda r: r[1] or 0.0)
            services = [SERVICE_LABELS.get(s, 'Other') for s, _a in svc[:2] if s]
            branch_names = Move.search(pdom).fm_cc_branch_id.mapped(
                lambda b: (b.name or '').split(' — ')[-1])
            p_open = open_dom + [('commercial_partner_id', '=', partner.id)]
            open_amt = Move._read_group(p_open, [], ['amount_residual:sum'])[0][0] or 0.0
            late = Move.search_count(p_open + [('invoice_date', '<', cut(60))])
            status = 'overdue' if late else ('pending' if open_amt else 'paid')
            accounts.append({
                'id': partner.id, 'name': partner.name, 'stream': stream or 'cash',
                'service': ' + '.join(services) or '—',
                'branch': '/'.join(dict.fromkeys(branch_names)) or '—',
                'value': amount or 0.0, 'open': open_amt, 'status': status,
                'drill': {'model': 'account.move',
                          'domain': self._inv_domain(ctx['states'], types=('out_invoice',))
                          + [('commercial_partner_id', '=', partner.id)],
                          'name': partner.name},
            })
        worst = None
        for partner, amount in Move._read_group(
                overdue_domain, ['commercial_partner_id'], ['amount_residual:sum'],
                order='amount_residual:sum desc', limit=1):
            if amount:
                worst = {'name': partner.name, 'amount': amount}

        return {
            'total': total, 'amc': amc, 'cash': cash,
            'amc_share': self._pct(amc, total, 0),
            'cash_share': self._pct(cash, total, 0),
            'overdue': overdue, 'aging': aging, 'accounts': accounts,
            'worst': worst,
            'drill_total': {'model': 'account.move', 'domain': open_dom,
                            'name': 'Open receivables'},
            'drill_amc': {'model': 'account.move',
                          'domain': open_dom + [('fm_cc_stream', '=', 'amc')],
                          'name': 'AMC receivables'},
            'drill_cash': {'model': 'account.move',
                           'domain': open_dom + [('fm_cc_stream', '=', 'cash')],
                           'name': 'Cash receivables'},
            'drill_overdue': {'model': 'account.move', 'domain': overdue_domain,
                              'name': 'Receivables over 60 days'},
        }

    # ------------------------------------------------------------------
    # new clients
    # ------------------------------------------------------------------

    def _new_clients(self, ctx):
        Move = self.env['account.move']
        first = {}
        for partner, first_date in Move._read_group(
                self._inv_domain(ctx['states'], types=('out_invoice',)),
                ['commercial_partner_id'], ['invoice_date:min']):
            if first_date:
                first[partner.id] = first_date
        start, end, prev_start = ctx['start'], ctx['end'], ctx['prev_start']
        new_ids = [p for p, d in first.items() if start <= d < end]
        prev = sum(1 for d in first.values() if prev_start <= d < start)
        by_branch = defaultdict(int)
        if new_ids:
            seen = set()
            for inv in Move.search(
                    self._inv_domain(ctx['states'], start, end, ('out_invoice',))
                    + [('commercial_partner_id', 'in', new_ids)],
                    order='invoice_date, id'):
                pid = inv.commercial_partner_id.id
                if pid not in seen:
                    seen.add(pid)
                    by_branch[inv.fm_cc_branch_id.id or False] += 1
        return {'count': len(new_ids), 'prev_count': prev, 'by_branch': by_branch,
                'ids': new_ids}

    # ------------------------------------------------------------------
    # 4 · Branch Scorecard
    # ------------------------------------------------------------------

    def _scorecard(self, ctx, revenue, credit, clients):
        Move = self.env['account.move']
        open_dom = self._open_domain(ctx)
        cut60 = _d(ctx['as_of'] - timedelta(days=60))
        rec, over = defaultdict(float), defaultdict(float)
        for branch, amount in Move._read_group(open_dom, ['fm_cc_branch_id'],
                                               ['amount_residual:sum']):
            rec[branch.id or False] += amount or 0.0
        for branch, amount in Move._read_group(
                open_dom + [('invoice_date', '<', cut60)],
                ['fm_cc_branch_id'], ['amount_residual:sum']):
            over[branch.id or False] += amount or 0.0

        rows = []
        ids = [b['id'] for b in ctx['branches']]
        if (revenue['by_branch'].get(False) and (
                revenue['by_branch'][False]['amc'] or revenue['by_branch'][False]['cash'])) \
                or rec.get(False):
            ids.append(False)
        for bid in ids:
            b = next((x for x in ctx['branches'] if x['id'] == bid), None)
            data = revenue['by_branch'].get(bid, {})
            amc, cash = data.get('amc', 0.0), data.get('cash', 0.0)
            amc_t = b['amc_target'] if b else 0.0
            cash_t = b['cash_target'] if b else 0.0
            rows.append({
                'id': bid, 'name': b['name'] if b else 'Unassigned',
                'manager': b['manager'] if b else '',
                'amc': amc, 'amc_target': amc_t,
                'amc_achieved': self._pct(amc, amc_t, 0),
                'cash': cash, 'cash_target': cash_t,
                'cash_achieved': self._pct(cash, cash_t, 0),
                'total': amc + cash, 'target': amc_t + cash_t,
                'achieved': self._pct(amc + cash, amc_t + cash_t, 0),
                'new_clients': clients['by_branch'].get(bid, 0),
                'receivable': rec.get(bid, 0.0), 'overdue': over.get(bid, 0.0),
                'drill': {'model': 'account.move',
                          'domain': revenue['domain'] + [('fm_cc_branch_id', '=', bid)],
                          'name': 'Invoices — %s' % (b['name'] if b else 'Unassigned')},
            })
        tot = {k: sum(r[k] for r in rows) for k in (
            'amc', 'amc_target', 'cash', 'cash_target', 'total', 'target',
            'new_clients', 'receivable', 'overdue')}
        tot['amc_achieved'] = self._pct(tot['amc'], tot['amc_target'], 0)
        tot['cash_achieved'] = self._pct(tot['cash'], tot['cash_target'], 0)
        tot['achieved'] = self._pct(tot['total'], tot['target'], 0)

        best = worst = None
        real = [r for r in rows if r['id']]
        both_above = [r for r in real if (r['amc_achieved'] or 0) >= 100
                      and (r['cash_achieved'] or 0) >= 100]
        if both_above:
            best = max(both_above, key=lambda r: r['achieved'] or 0)
        both_below = [r for r in real if r['target'] and (r['amc_achieved'] or 0) < 100
                      and (r['cash_achieved'] or 0) < 100]
        if both_below:
            worst = max(both_below, key=lambda r: r['overdue'])
        top = max(real, key=lambda r: r['total']) if real and any(r['total'] for r in real) else None
        late = max(real, key=lambda r: r['overdue']) if real and any(r['overdue'] for r in real) else None
        return {'rows': rows, 'totals': tot, 'best': best, 'worst': worst,
                'top': top, 'late': late,
                'max_bar': max([max(r['total'], r['target']) for r in rows] + [1])}

    # ------------------------------------------------------------------
    # 5 & 6 · Services
    # ------------------------------------------------------------------

    def _services(self, ctx):
        Line = self.env['account.move.line']
        domain = ([('move_id.fm_cc_service', '=', self._svc())] if self._svc() else []) + (
            [('move_id.fm_cc_branch_id', '=', self._br())] if self._br() else []) + [
                  ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
                  ('parent_state', 'in', list(ctx['states'])),
                  ('move_id.invoice_date', '>=', _d(ctx['start'])),
                  ('move_id.invoice_date', '<', _d(ctx['end'])),
                  ('display_type', '=', 'product')]
        data = defaultdict(lambda: {'amc': 0.0, 'cash': 0.0, 'branches': defaultdict(
            lambda: {'amc': 0.0, 'cash': 0.0})})
        for service, stream, branch, balance in Line._read_group(
                domain, ['fm_cc_service', 'fm_cc_stream', 'fm_cc_branch_id'],
                ['balance:sum']):
            amount = -(balance or 0.0)
            key = service or 'other'
            stream = stream or 'cash'
            data[key][stream] += amount
            data[key]['branches'][branch.id or False][stream] += amount
        grand = sum(v['amc'] + v['cash'] for v in data.values())
        rows = []
        for key, v in data.items():
            total = v['amc'] + v['cash']
            if not total:
                continue
            rows.append({
                'key': key, 'label': SERVICE_LABELS.get(key, 'Other'),
                'amc': v['amc'], 'cash': v['cash'], 'total': total,
                'share': self._pct(total, grand),
                'amc_share': self._pct(v['amc'], total, 0),
                'branches': {str(b): {'total': x['amc'] + x['cash'],
                                      'amc_share': self._pct(x['amc'], x['amc'] + x['cash'], 0),
                                      'drill': {'model': 'account.move.line',
                                                'domain': domain + [('fm_cc_service', '=', key),
                                                                    ('fm_cc_branch_id', '=', b)],
                                                'name': SERVICE_LABELS.get(key, 'Other')}}
                             for b, x in v['branches'].items() if x['amc'] + x['cash']},
                'drill': {'model': 'account.move.line',
                          'domain': domain + [('fm_cc_service', '=', key)],
                          'name': SERVICE_LABELS.get(key, 'Other')},
            })
        rows.sort(key=lambda r: -r['total'])

        columns = [{'id': b['id'], 'key': str(b['id']), 'name': b['name']}
                   for b in ctx['branches']]
        if any('False' in r['branches'] for r in rows):
            columns.append({'id': False, 'key': 'False', 'name': 'Unassigned'})
        for col in columns:
            col['services'] = sum(1 for r in rows if col['key'] in r['branches'])
            col['total'] = sum(r['branches'].get(col['key'], {}).get('total', 0.0)
                               for r in rows)

        notes = {}
        if rows:
            top3 = rows[:3]
            t3 = sum(r['total'] for r in top3)
            amc3 = sum(r['amc'] for r in top3)
            notes['top'] = {'names': [r['label'] for r in top3],
                            'share': self._pct(t3, grand, 0),
                            'mostly_amc': amc3 >= t3 / 2}
            cashy = [r['label'] for r in rows if (r['amc_share'] or 0) <= 15 and r['total']]
            notes['cashy'] = cashy[:4]
            real_cols = [c for c in columns if c['id'] and c['services']]
            if real_cols:
                few = min(real_cols, key=lambda c: c['services'])
                notes['fewest'] = {'name': few['name'], 'services': few['services'],
                                   'total': few['total']}
                only = []
                for r in rows:
                    present = [c for c in real_cols if c['key'] in r['branches']]
                    if len(present) == 1 and len(real_cols) > 1:
                        only.append((present[0]['name'], r['label']))
                if only:
                    name = max({n for n, _l in only}, key=lambda n: sum(
                        1 for x, _l in only if x == n))
                    notes['exclusive'] = {'name': name,
                                          'services': [l for n, l in only if n == name]}
        return {'rows': rows, 'columns': columns, 'grand': grand,
                'max': max([r['total'] for r in rows] + [1]), 'notes': notes}

    # ------------------------------------------------------------------
    # 8 · Sales Team
    # ------------------------------------------------------------------

    def _sales_team(self, ctx):
        start, end = ctx['start'], ctx['end']
        amc_deals = defaultdict(int)
        amc_ids = defaultdict(list)
        users = {}
        for c in self._contracts():
            if c['start'] and start <= c['start'] < end and c['user']:
                amc_deals[c['user'].id] += 1
                amc_ids[c['user'].id].append(c['id'])
                users[c['user'].id] = c['user']
        cash_deals = defaultdict(int)
        Move = self.env['account.move']
        cash_dom = self._inv_domain(ctx['states'], start, end, ('out_invoice',)) \
            + [('fm_cc_stream', '=', 'cash')]
        for user, count in Move._read_group(
                cash_dom, ['invoice_user_id'], ['__count']):
            if user:
                cash_deals[user.id] += count
                users[user.id] = user
        targets = {}
        for t in self.env['fm.cc.sales.target'].search([('deal_target', '>', 0)]):
            targets[t.user_id.id] = t.deal_target
            users[t.user_id.id] = t.user_id
        rows = []
        for uid, user in users.items():
            a, c = amc_deals.get(uid, 0), cash_deals.get(uid, 0)
            total = a + c
            target = targets.get(uid, 0)
            drill_amc = {'model': 'sale.order',
                         'domain': [('id', 'in', amc_ids.get(uid, []))],
                         'name': 'AMC deals — %s' % user.name}
            drill_cash = {'model': 'account.move',
                          'domain': cash_dom + [('invoice_user_id', '=', uid)],
                          'name': 'Cash deals — %s' % user.name}
            rows.append({
                'id': uid, 'name': user.name, 'amc': a, 'cash': c, 'total': total,
                'target': target, 'achieved': self._pct(total, target, 0),
                'amc_mix': self._pct(a, total, 0),
                'drill_amc': drill_amc, 'drill_cash': drill_cash,
                'drill': drill_amc if a >= c and a else drill_cash,
            })
        rows.sort(key=lambda r: (-r['total'], r['name']))
        above = [r['name'] for r in rows if r['target'] and total_ok(r)]
        below = [r for r in rows if r['target'] and not total_ok(r)]
        lowest = min(below, key=lambda r: r['achieved'] or 0) if below else None
        return {'rows': rows, 'above': above, 'below': [r['name'] for r in below],
                'lowest': lowest,
                'max_bar': max([max(r['total'], r['target']) for r in rows] + [1])}

    # ------------------------------------------------------------------
    # 9 · Expenses & Margin
    # ------------------------------------------------------------------

    def _expense_domain(self, ctx, start, end):
        branch = [('move_id.branch_id', '=', self._br())] if self._br() else []
        return branch + [('parent_state', 'in', list(ctx['states'])),
                ('account_id.account_type', 'like', 'expense'),
                ('date', '>=', _d(start)), ('date', '<', _d(end))]

    def _expenses(self, ctx, revenue):
        Line = self.env['account.move.line']
        start, end, prev_start = ctx['start'], ctx['end'], ctx['prev_start']
        cur_dom = self._expense_domain(ctx, start, end)
        prev = {}
        for account, balance in Line._read_group(
                self._expense_domain(ctx, prev_start, start), ['account_id'], ['balance:sum']):
            prev[account.id] = balance or 0.0
        rows = []
        for account, balance, count in Line._read_group(
                cur_dom, ['account_id'], ['balance:sum', '__count']):
            if not balance:
                continue
            dom = cur_dom + [('account_id', '=', account.id)]
            moves = Line.search(dom).move_id
            bills = moves.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))
            if bills and all(b.payment_state in ('paid', 'in_payment', 'reversed')
                             for b in bills):
                status = 'paid'
            elif bills:
                status = 'pending'
            else:
                status = 'booked' if all(m.state == 'posted' for m in moves) else 'pending'
            rows.append({
                'id': account.id, 'name': account.name or account.code,
                'amount': balance, 'prev': prev.get(account.id, 0.0),
                'status': status,
                'drill': {'model': 'account.move.line', 'domain': dom,
                          'name': account.name},
            })
        rows.sort(key=lambda r: -r['amount'])
        if len(rows) > 8:
            rest = rows[7:]
            rows = rows[:7] + [{
                'id': False, 'name': 'Other expenses',
                'amount': sum(r['amount'] for r in rest),
                'prev': sum(r['prev'] for r in rest),
                'status': 'paid' if all(r['status'] == 'paid' for r in rest) else 'pending',
                'drill': {'model': 'account.move.line',
                          'domain': cur_dom + [('account_id', 'in', [r['id'] for r in rest])],
                          'name': 'Other expenses'},
            }]
        total_rev = revenue['amc'] + revenue['cash']
        total = sum(r['amount'] for r in rows)
        prev_total = sum(prev.values())
        for r in rows:
            r['revenue_pct'] = self._pct(r['amount'], total_rev)
            r['delta'] = self._delta(r['amount'], r['prev'])
        payroll = sum(r['amount'] for r in rows
                      if any(w in (r['name'] or '').casefold() for w in PAYROLL_WORDS))
        profit = total_rev - total
        # No expense booked = no margin to speak of, not a 100% margin.
        margin = self._pct(profit, total_rev) if total else None
        if not total:
            profit = None
        target = self.env.company.fm_cc_margin_target or 0.0
        growing = sorted([r for r in rows if r['delta'] and r['delta'] > 0],
                         key=lambda r: -r['delta'])[:2]
        budget = self._budget(ctx, total)
        return {
            'budget': budget,
            'total': total, 'delta': self._delta(total, prev_total),
            'profit': profit, 'margin': margin, 'margin_target': target,
            'margin_gap': round(target - margin, 1) if margin is not None and target else None,
            'payroll_share': self._pct(payroll, total, 0),
            'rows': rows, 'growing': [{'name': r['name'], 'delta': r['delta']} for r in growing],
            'max': max([r['amount'] for r in rows] + [1]),
            'drill': {'model': 'account.move.line', 'domain': cur_dom,
                      'name': 'Expenses this month'},
        }

    def _budget(self, ctx, actual):
        """Budget vs actual for the month: the client's budget sheet
        (fm.cc.budget) against the expenses booked. Actual is the month's
        total only -- expenses carry no location, so it is not split."""
        Budget = self.env['fm.cc.budget']
        labels = dict(Budget._fields['location'].selection)
        domain = [('month', '=', ctx['start'])]
        location = False
        if self._br():
            name = (self.env['fm.branch'].browse(self._br()).name or '').casefold()
            location = next((k for k in labels if k in name), False)
            if location:
                domain.append(('location', '=', location))
        by_loc = {}
        for line in Budget.search(domain):
            row = by_loc.setdefault(line.location, {
                'key': line.location, 'label': labels.get(line.location, line.location),
                'payroll': 0.0, 'other': 0.0, 'total': 0.0})
            row['payroll' if line.cost_group == 'payroll' else 'other'] += line.amount
            row['total'] += line.amount
        order = [k for k, _l in Budget._fields['location'].selection]
        rows = sorted(by_loc.values(), key=lambda r: order.index(r['key']))
        planned = sum(r['total'] for r in rows)
        if not planned:
            return {'has': False}
        return {
            'has': True,
            'planned': planned,
            'payroll': sum(r['payroll'] for r in rows),
            'other': sum(r['other'] for r in rows),
            'actual': actual,
            'variance': planned - actual,
            'used': self._pct(actual, planned, 0),
            'rows': rows,
            'branch_note': bool(self._br()),
            'drill': {'model': 'fm.cc.budget', 'domain': domain,
                      'name': 'Budget %s' % ctx['start'].strftime('%b %Y')},
        }

    # ------------------------------------------------------------------
    # 10 · Cash & Bank
    # ------------------------------------------------------------------

    def _bank(self, ctx):
        Line = self.env['account.move.line']
        end = ctx['end']
        journals = self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')),
             ('company_id', 'in', self.env.companies.ids)])
        accounts = journals.mapped('default_account_id')
        if not accounts:
            return {'balance': 0.0, 'accounts': [], 'transactions': [],
                    'inflow': 0.0, 'outflow': 0.0, 'net': 0.0,
                    'inflow_delta': None, 'outflow_delta': None}
        rows = []
        for journal in journals:
            acc = journal.default_account_id
            if not acc:
                continue
            dom = [('account_id', '=', acc.id), ('parent_state', '=', 'posted'),
                   ('date', '<', _d(end))]
            bal = Line._read_group(dom, [], ['balance:sum'])[0][0] or 0.0
            number = journal.bank_account_id.acc_number if journal.bank_account_id else ''
            label = journal.name
            if journal.bank_account_id and journal.bank_account_id.bank_id:
                label = '%s — %s' % (journal.bank_account_id.bank_id.name, journal.name)
            rows.append({
                'id': journal.id, 'name': label,
                'company': journal.company_id.name,
                'number': ('•••• ' + number[-4:]) if number else (
                    'Cash' if journal.type == 'cash' else '—'),
                'type': journal.type, 'balance': bal,
                'drill': {'model': 'account.move.line', 'domain': dom,
                          'name': journal.name},
            })
        rows.sort(key=lambda r: (r['type'] != 'bank', -r['balance']))
        ytd_start = date(ctx['start'].year, 1, 1)
        base = [('account_id', 'in', accounts.ids), ('parent_state', '=', 'posted')]

        def flow(s, e):
            dom = base + [('date', '>=', _d(s)), ('date', '<', _d(e))]
            debit, credit = Line._read_group(dom, [], ['debit:sum', 'credit:sum'])[0]
            return debit or 0.0, credit or 0.0
        inflow, outflow = flow(ytd_start, end)
        ly_in, ly_out = flow(ytd_start - relativedelta(years=1), end - relativedelta(years=1))

        transactions = []
        for line in Line.search(base + [('date', '<', _d(end))],
                                order='date desc, id desc', limit=8):
            move = line.move_id
            stream = False
            status = 'cleared'
            pay = move.origin_payment_id if 'origin_payment_id' in move._fields else False
            if pay:
                invoices = pay.reconciled_invoice_ids
                streams = set(invoices.mapped('fm_cc_stream'))
                stream = 'amc' if 'amc' in streams else ('cash' if streams else False)
                status = 'processing' if pay.state == 'in_process' else 'cleared'
            transactions.append({
                'id': line.id,
                'date': line.date.strftime('%d %b'),
                'account': line.journal_id.name,
                'description': move.ref or line.name or move.name,
                'partner': line.partner_id.name or '',
                'stream': stream, 'amount': line.balance, 'status': status,
                'drill': {'model': 'account.move', 'domain': [('id', '=', move.id)],
                          'name': move.name},
            })
        balance = sum(r['balance'] for r in rows)
        return {
            'balance': balance, 'accounts': rows,
            'account_count': len(rows),
            'inflow': inflow, 'outflow': outflow, 'net': inflow - outflow,
            'inflow_delta': self._delta(inflow, ly_in),
            'outflow_delta': self._delta(outflow, ly_out),
            'transactions': transactions,
            'year': ctx['start'].year,
        }


def total_ok(row):
    return (row['achieved'] or 0) >= 100
