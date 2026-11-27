# -*- coding: utf-8 -*-
"""Data provider for the Budget Dashboard ("One Budget, Every Branch").

A sibling of the CEO Dashboard, under the same app and in the same style,
laid out after the client's Budget Dashboard PDF: 1 Monthly Budget,
2 Where the Money Goes, 3 Branch Scorecard, 4 Team & Payroll,
5 Renewals & Compliance, 6 Running Costs, 7 Budget Checks, and 8 Budget
vs Actual, which the PDF could not have.

The plan is fm.cc.budget (month x location x cost group). Actuals are the
expense lines booked in Odoo, by the same rule as the CEO Dashboard's
Expenses & Margin section. Expenses carry no location of their own, only
the move's branch, so a location filter narrows actuals to moves booked to
that branch and the Pakistan office has no actuals at all.
"""
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .budget import COST_GROUPS, LOCATIONS, PAYMENT_PLANS

UAE = ('ajman', 'sharjah', 'dubai', 'fujairah')


def _d(value):
    return fields.Date.to_string(value)


class FmCcBudgetDashboard(models.AbstractModel):
    _name = 'fm.cc.budget.dashboard'
    _description = 'Budget Dashboard data provider'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @api.model
    def _pct(self, part, whole, digits=0):
        return round(100.0 * part / whole, digits) if whole else None

    @api.model
    def _branch_map(self):
        """location key -> fm.branch id, matched on emirate or name."""
        out = {}
        for b in self.env['fm.branch'].search([]):
            label = (b.name or '').casefold()
            for key in UAE:
                if key not in out and (b.emirate == key or key in label):
                    out[key] = b.id
        return out

    @api.model
    def _window(self, start):
        """The 12-month plan window. Default: the one holding today, else
        the earliest budget month on file."""
        Budget = self.env['fm.cc.budget']
        if start:
            try:
                y, m = (int(x) for x in str(start).split('-')[:2])
                return date(y, m, 1)
            except (TypeError, ValueError):
                pass
        today = fields.Date.context_today(self).replace(day=1)
        first = Budget.search([], order='month asc', limit=1).month
        if not first:
            return today
        # step from the first plan month in 12-month windows up to today
        s = first
        while s + relativedelta(months=12) <= today:
            s += relativedelta(months=12)
        if not Budget.search_count([('month', '>=', s), ('month', '<', s + relativedelta(months=12))]):
            s = first
        return s

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    @api.model
    def get_data(self, start=False, location=False):
        Budget = self.env['fm.cc.budget']
        loc_labels = dict(LOCATIONS)
        grp_labels = dict(COST_GROUPS)
        if location not in loc_labels:
            location = False
        w_start = self._window(start)
        w_end = w_start + relativedelta(months=12)
        dom = [('month', '>=', w_start), ('month', '<', w_end)]
        if location:
            dom.append(('location', '=', location))
        lines = Budget.search(dom)
        months = sorted(set(lines.mapped('month')))
        locs = [k for k, _l in LOCATIONS if k in set(lines.mapped('location'))]
        groups = [k for k, _l in COST_GROUPS if k in set(lines.mapped('cost_group'))]

        cell = defaultdict(float)     # (month, loc)
        lg = defaultdict(float)       # (loc, group)
        mg = defaultdict(float)       # (month, group)
        for ln in lines:
            cell[(ln.month, ln.location)] += ln.amount
            lg[(ln.location, ln.cost_group)] += ln.amount
            mg[(ln.month, ln.cost_group)] += ln.amount
        total = sum(lines.mapped('amount'))
        n = len(months) or 1
        month_tot = {m: sum(cell[(m, l)] for l in locs) for m in months}
        avg = total / n
        peak = max(months, key=lambda m: month_tot[m]) if months else None
        low = min(months, key=lambda m: month_tot[m]) if months else None
        payroll = sum(v for (l, g), v in lg.items() if g == 'payroll')
        loc_tot = {l: sum(lg[(l, g)] for g in groups) for l in locs}
        top_loc = max(locs, key=lambda l: loc_tot[l]) if locs else None

        def drill(extra=None, name='Budget'):
            return {'model': 'fm.cc.budget', 'domain': dom + (extra or []), 'name': name}

        def mlabel(m, fmt='%b %Y'):
            return m.strftime(fmt) if m else ''

        # 1 · monthly
        monthly = [{
            'key': _d(m), 'label': mlabel(m), 'short': mlabel(m, '%b'),
            'cells': [cell[(m, l)] for l in locs], 'total': month_tot[m],
            'drill': drill([('month', '=', _d(m))], 'Budget %s' % mlabel(m)),
        } for m in months]

        # 2 · groups
        group_rows = [{
            'key': g, 'label': grp_labels[g],
            'total': sum(mg[(m, g)] for m in months),
        } for g in groups]
        for r in group_rows:
            r['per_month'] = r['total'] / n
            r['share'] = self._pct(r['total'], total, 1)
            r['drill'] = drill([('cost_group', '=', r['key'])], 'Budget · %s' % r['label'])
        group_rows.sort(key=lambda r: -r['total'])

        # 3 · scorecard
        score = [{
            'key': l, 'label': loc_labels[l],
            'cells': [lg[(l, g)] for g in groups], 'total': loc_tot[l],
            'per_month': loc_tot[l] / n, 'share': self._pct(loc_tot[l], total),
            'drill': drill([('location', '=', l)], 'Budget · %s' % loc_labels[l]),
        } for l in locs]

        # categories (2, 6, 7)
        Cat = self.env['fm.cc.budget.category']
        plan_labels = dict(PAYMENT_PLANS)
        by_cat = defaultdict(float)
        for ln in lines:
            by_cat[ln.category_id.id] += ln.amount
        cat_rows = []
        for c in Cat.search([]):
            t = by_cat.get(c.id, 0.0)
            cat_rows.append({
                'id': c.id, 'label': c.name, 'plan': plan_labels.get(c.payment_plan, ''),
                'total': t, 'per_month': t / n, 'share': self._pct(t, total, 1),
                'drill': drill([('category_id', '=', c.id)], 'Budget · %s' % c.name),
            })
        if by_cat.get(False):
            cat_rows.append({'id': 0, 'label': 'Without a category', 'plan': '',
                             'total': by_cat[False], 'per_month': by_cat[False] / n,
                             'share': self._pct(by_cat[False], total, 1),
                             'drill': drill([('category_id', '=', False)], 'Budget · no category')})
        cat_rows.sort(key=lambda r: (-r['total'], r['label']))
        nobudget = [r['label'] for r in cat_rows if not r['total']]

        # 4 · payroll and visas
        team = self._team(locs, lg, n, payroll, w_end, location)

        # 5 · renewals and compliance
        renewals = self._renewals(w_end, location, by_cat)

        # 6 · running costs
        running = self._running(lines, months, locs, n)

        # 7 · budget checks
        # the sheet's detail tabs are company-wide, so the checks always are
        all_lines = Budget.search([('month', '>=', w_start), ('month', '<', w_end)]) if location else lines
        all_total = sum(all_lines.mapped('amount'))
        checks = self._checks(all_lines, months, n, all_total)

        # 8 · budget vs actual
        actual = self._actual(months, month_tot, location)

        return {
            'company_id': self.env.company.id,
            'tagline': self.env.company.fm_cc_tagline or '',
            'has': bool(lines),
            'start': w_start.strftime('%Y-%m'),
            'period': '%s – %s' % (mlabel(months[0]), mlabel(months[-1])) if months else
                      '%s – %s' % (mlabel(w_start), mlabel(w_end - relativedelta(months=1))),
            'month_count': len(months),
            'location': location,
            'location_label': loc_labels.get(location, ''),
            'location_options': [{'key': k, 'label': v} for k, v in LOCATIONS],
            'locations': [{'key': l, 'label': loc_labels[l]} for l in locs],
            'groups': [{'key': g, 'label': grp_labels[g]} for g in groups],
            'uae_count': len([l for l in locs if l in UAE]),
            'has_pakistan': 'pakistan' in locs,
            'generated': fields.Datetime.context_timestamp(
                self, fields.Datetime.now()).strftime('%d %b %Y, %H:%M'),
            'cover': {
                'total': total, 'avg': avg,
                'payroll': payroll, 'payroll_share': self._pct(payroll, total),
                'other': total - payroll, 'other_share': self._pct(total - payroll, total),
                'peak': month_tot.get(peak, 0.0), 'peak_label': mlabel(peak),
                'low': month_tot.get(low, 0.0), 'low_label': mlabel(low),
                'top_loc': loc_labels.get(top_loc, ''), 'top_loc_total': loc_tot.get(top_loc, 0.0),
                'top_loc_share': self._pct(loc_tot.get(top_loc, 0.0), total),
                'drill': drill(name='Budget %s' % w_start.year),
            },
            'monthly': monthly,
            'loc_totals': [loc_tot[l] for l in locs],
            'group_rows': group_rows,
            'group_max': max([r['total'] for r in group_rows] + [1]),
            'group_totals': [sum(lg[(l, g)] for l in locs) for g in groups],
            'score': score,
            'categories': cat_rows,
            'nobudget': nobudget,
            'team': team,
            'renewals': renewals,
            'running': running,
            'checks': checks,
            'actual': actual,
            'today': fields.Date.context_today(self).strftime('%d %b %Y'),
        }

    # ------------------------------------------------------------------
    # 4 · Team & Payroll
    # ------------------------------------------------------------------

    def _emp_location(self, emp, bmap):
        """location key of an employee: their FM branch, else a work
        location naming exactly one branch ("Ajman"; not "Ajman & Sharjah")."""
        rev = {v: k for k, v in bmap.items()}
        if 'fm_branch_id' in emp._fields and emp.fm_branch_id:
            return rev.get(emp.fm_branch_id.id)
        name = (emp.work_location_id.name or '').casefold()
        hits = [k for k in UAE if k in name]
        return hits[0] if len(hits) == 1 else None

    @api.model
    def _can_hr(self):
        return self.env.user.has_group('hr.group_hr_user')

    def _status(self, expiry, today, soon=45):
        if not expiry:
            return 'none', None
        days = (expiry - today).days
        return ('expired' if days < 0 else 'soon' if days <= soon else 'later'), days

    def _team(self, locs, lg, n, payroll, w_end, location):
        bmap = self._branch_map()
        # counts are not personal data; dates are, and need Employees rights
        emps = self.env['hr.employee'].sudo().search([('company_id', 'in', self.env.companies.ids)])
        where = {e.id: self._emp_location(e, bmap) for e in emps}
        rows = []
        for l in locs:
            plan = lg[(l, 'payroll')]
            rows.append({
                'key': l, 'label': dict(LOCATIONS)[l],
                'staff': len([1 for e in emps if where[e.id] == l]) if l in UAE else None,
                'per_month': plan / n, 'total': plan,
                'share': self._pct(plan, payroll),
            })
        today = fields.Date.context_today(self)
        visa_cat = self.env.ref('fm_command_centre.budget_cat_visa_renewal', raise_if_not_found=False)
        unit = visa_cat.unit_cost if visa_cat else 0.0
        visas = []
        if self._can_hr():
            for e in emps.filtered(lambda e: e.visa_expire and e.visa_expire < w_end).sorted('visa_expire'):
                if location and where[e.id] != location:
                    continue
                status, days = self._status(e.visa_expire, today)
                visas.append({
                    'id': e.id, 'name': e.name,
                    'branch': dict(LOCATIONS).get(where[e.id], e.work_location_id.name or ''),
                    'expiry': e.visa_expire.strftime('%d %b %Y'),
                    'days': days, 'status': status, 'cost': unit,
                    'due': e.visa_expire.strftime('%b %Y'),
                })
        return {
            'rows': rows,
            'max': max([r['per_month'] for r in rows] + [1]),
            'per_month': payroll / n,
            'staff': len(emps),
            'unassigned': len([1 for e in emps if not where[e.id]]),
            'visas': visas,
            'can_hr': self._can_hr(),
            'unit': unit,
            'visa_cost': unit * len(visas),
            'expired': len([v for v in visas if v['status'] == 'expired']),
            'expired_names': [v['name'] for v in visas if v['status'] == 'expired'],
            'due': len([v for v in visas if v['status'] != 'expired']),
            'emp_drill': {'model': 'hr.employee', 'domain': [], 'name': 'Employees'},
        }

    # ------------------------------------------------------------------
    # 5 · Renewals & Compliance
    # ------------------------------------------------------------------

    def _renewals(self, w_end, location, by_cat):
        today = fields.Date.context_today(self)
        bmap = self._branch_map()
        rev = {v: k for k, v in bmap.items()}
        vehicles = []
        fleet = 'fleet.vehicle' in self.env and \
            'fm_registration_expiry' in self.env['fleet.vehicle']._fields
        if fleet:
            dom = [('company_id', 'in', self.env.companies.ids + [False])]
            if location:
                dom.append(('fm_branch_id', '=', bmap.get(location, 0)))
            for v in self.env['fleet.vehicle'].search(dom):
                status, days = self._status(v.fm_registration_expiry, today)
                vehicles.append({
                    'id': v.id, 'name': v.license_plate or v.name,
                    'branch': dict(LOCATIONS).get(rev.get(v.fm_branch_id.id), v.fm_branch_id.name or ''),
                    'reg': v.fm_registration_expiry and v.fm_registration_expiry.strftime('%d %b %Y'),
                    'ins': v.fm_insurance_expiry and v.fm_insurance_expiry.strftime('%d %b %Y'),
                    'reg_date': v.fm_registration_expiry, 'status': status, 'days': days,
                    'due': v.fm_registration_expiry and v.fm_registration_expiry.strftime('%b %Y'),
                })
            vehicles.sort(key=lambda r: (r['reg_date'] is None, r['reg_date'] or today))
            for r in vehicles:
                r.pop('reg_date')
        cards = []
        if self._can_hr():
            emps = self.env['hr.employee'].search([
                ('company_id', 'in', self.env.companies.ids), '|',
                ('fm_health_card_expiry', '!=', False), ('fm_dm_card_expiry', '!=', False)])
            for e in emps.sorted('name'):
                if location and self._emp_location(e, bmap) != location:
                    continue
                dates = [d for d in (e.fm_health_card_expiry, e.fm_dm_card_expiry) if d]
                status, days = self._status(min(dates), today)
                cards.append({
                    'id': e.id, 'name': e.name,
                    'health': e.fm_health_card_expiry and e.fm_health_card_expiry.strftime('%d %b %Y'),
                    'dm': e.fm_dm_card_expiry and e.fm_dm_card_expiry.strftime('%d %b %Y'),
                    'status': status, 'days': days,
                })
        hcat = self.env.ref('fm_command_centre.budget_cat_health_dm', raise_if_not_found=False)
        return {
            'fleet': fleet,
            'vehicles': vehicles,
            'veh_expired': [v['name'] for v in vehicles if v['status'] == 'expired'],
            'veh_soon': [v['name'] for v in vehicles if v['status'] == 'soon'],
            'cards': cards,
            'cards_expired': len([c for c in cards if c['status'] == 'expired']),
            'cards_budget': by_cat.get(hcat.id, 0.0) if hcat else 0.0,
            'can_hr': self._can_hr(),
            'veh_drill': {'model': 'fleet.vehicle', 'domain': [], 'name': 'Vehicles'} if fleet else False,
        }

    # ------------------------------------------------------------------
    # 6 · Running Costs
    # ------------------------------------------------------------------

    def _running(self, lines, months, locs, n):
        loc_labels = dict(LOCATIONS)
        monthly = lines.filtered(lambda l: l.category_id.payment_plan == 'monthly'
                                 and l.cost_group != 'payroll')
        items = defaultdict(lambda: defaultdict(float))
        for ln in monthly:
            items[ln.category_id][ln.location] += ln.amount
        rows = []
        for cat in sorted(items, key=lambda c: -sum(items[c].values())):
            cells = [items[cat].get(l, 0.0) / n for l in locs]
            rows.append({'id': cat.id, 'label': cat.name, 'cells': cells, 'total': sum(cells)})
        col = [sum(r['cells'][i] for r in rows) for i in range(len(locs))]

        def per_month(name):
            r = next((r for r in rows if r['label'] == name), None)
            if not r:
                return 0.0, 0.0
            uae = [r['cells'][i] for i, l in enumerate(locs) if l in UAE and r['cells'][i]]
            return r['total'], (sum(uae) / len(uae) if uae else 0.0)

        rent = []
        rent_lines = lines.filtered(lambda l: l.cost_group == 'rent')
        for l in locs:
            mine = rent_lines.filtered(lambda r: r.location == l and r.amount)
            if not mine:
                continue
            paid = sorted(set(mine.mapped('month')))
            amounts = [sum(mine.filtered(lambda r: r.month == m).mapped('amount')) for m in paid]
            each = max(set(amounts), key=amounts.count)
            rent.append({'key': l, 'label': loc_labels[l],
                         'months': ', '.join(m.strftime('%b') for m in paid),
                         'each': each, 'count': len(paid), 'total': sum(amounts)})
        yearly = lines.filtered(lambda l: l.category_id.payment_plan == 'yearly')
        fees = defaultdict(lambda: defaultdict(float))
        for ln in yearly:
            fees[ln.category_id][ln.month] += ln.amount
        cal = [{'label': c.name, 'cells': [fees[c].get(m, 0.0) for m in months],
                'total': sum(fees[c].values()), 'seq': c.sequence}
               for c in fees if sum(fees[c].values())]
        cal.sort(key=lambda r: r['seq'])
        fuel, fuel_br = per_month('Fuel')
        chem, chem_br = per_month('Chemical')
        return {
            'rows': rows, 'col': col, 'total': sum(col),
            'fuel': fuel, 'fuel_branch': fuel_br,
            'chem': chem, 'chem_branch': chem_br,
            'rent': rent, 'rent_total': sum(r['total'] for r in rent),
            'calendar': cal,
            'months': [m.strftime('%b') for m in months],
            'cal_cols': [sum(r['cells'][i] for r in cal) for i in range(len(months))],
        }

    # ------------------------------------------------------------------
    # 7 · Budget Checks
    # ------------------------------------------------------------------

    def _checks(self, lines, months, n, total):
        rows = []
        by_cat = defaultdict(float)
        for ln in lines:
            by_cat[ln.category_id.id] += ln.amount
        for c in self.env['fm.cc.budget.category'].search([]):
            plan_total = by_cat.get(c.id, 0.0)
            if not c.detail_amount:
                if not plan_total and c.detail_note:
                    rows.append({'label': c.name, 'detail': c.detail_note, 'plan': 'AED 0',
                                 'diff': None, 'diff_label': 'not budgeted', 'status': 'missing'})
                continue
            if c.detail_basis == 'month':
                plan = plan_total / n
                diff = plan - c.detail_amount
                detail = c.detail_note or 'AED %s a month' % '{:,.0f}'.format(c.detail_amount)
                plan_s = 'AED %s a month' % '{:,.0f}'.format(plan)
                diff_s = '%s%s / month' % ('+' if diff > 0 else '−', '{:,.0f}'.format(abs(diff)))
            else:
                plan = plan_total
                diff = plan - c.detail_amount
                detail = c.detail_note or 'AED %s a year' % '{:,.0f}'.format(c.detail_amount)
                plan_s = 'AED %s' % '{:,.0f}'.format(plan)
                diff_s = '%s%s' % ('+' if diff > 0 else '−', '{:,.0f}'.format(abs(diff)))
            if abs(diff) < 1:
                status = 'ok'
            else:
                status = 'higher' if diff > 0 else 'lower'
            rows.append({'label': c.name, 'detail': detail, 'plan': plan_s,
                         'diff': diff, 'diff_label': diff_s, 'status': status,
                         'basis': c.detail_basis})
        order = {'higher': 0, 'lower': 1, 'missing': 2, 'ok': 3}
        rows.sort(key=lambda r: (order[r['status']], -abs(r['diff'] or 0)))
        yearly_gap = sum(-r['diff'] for r in rows if r['status'] == 'lower' and r.get('basis') == 'year')
        monthly_gap = sum(r['diff'] for r in rows if r['status'] == 'higher' and r.get('basis') == 'month')
        return {
            'rows': rows,
            'review': len([r for r in rows if r['status'] != 'ok']),
            'higher': len([r for r in rows if r['status'] == 'higher']),
            'higher_names': [r['label'] for r in rows if r['status'] == 'higher'],
            'lower': len([r for r in rows if r['status'] == 'lower']),
            'missing': len([r for r in rows if r['status'] == 'missing']),
            'yearly_gap': yearly_gap, 'monthly_gap': monthly_gap,
            'months': len(months),
            'full_year': total + (12 - len(months)) * (total / n) if months and len(months) < 12 else total,
            'first': months[0].strftime('%b %Y') if months else '',
            'last': months[-1].strftime('%b %Y') if months else '',
            'missing_month': (months[-1] + relativedelta(months=1)).strftime('%b %Y')
                             if months and len(months) < 12 else '',
        }

    # ------------------------------------------------------------------
    # 5 · Budget vs Actual
    # ------------------------------------------------------------------

    def _actual(self, months, month_tot, location):
        Line = self.env['account.move.line']
        if not months:
            return {'rows': [], 'budget': 0.0, 'actual': 0.0}
        base = [('parent_state', 'in', ['draft', 'posted']),
                ('account_id.account_type', 'like', 'expense')]
        branch_note = False
        if location == 'pakistan':
            base.append(('id', '=', 0))
            branch_note = 'pakistan'
        elif location:
            bid = self._branch_map().get(location)
            base.append(('move_id.branch_id', '=', bid or 0))
            branch_note = 'branch'
        start, end = months[0], months[-1] + relativedelta(months=1)
        booked = defaultdict(float)
        for month, balance in Line._read_group(
                base + [('date', '>=', _d(start)), ('date', '<', _d(end))],
                ['date:month'], ['balance:sum']):
            booked[month.replace(day=1)] += balance or 0.0
        today = fields.Date.context_today(self)
        rows = []
        cum_b = cum_a = 0.0
        for m in months:
            nxt = m + relativedelta(months=1)
            closed = m <= today
            b, a = month_tot[m], booked.get(m, 0.0)
            if closed:
                cum_b += b
                cum_a += a
            rows.append({
                'key': _d(m), 'label': m.strftime('%b %Y'),
                'budget': b, 'actual': a if closed else None,
                'variance': (b - a) if closed else None,
                'used': self._pct(a, b) if closed else None,
                'future': not closed,
                'drill': {'model': 'account.move.line',
                          'domain': base + [('date', '>=', _d(m)), ('date', '<', _d(nxt))],
                          'name': 'Expenses %s' % m.strftime('%b %Y')},
            })
        return {
            'rows': rows,
            'budget': cum_b, 'actual': cum_a,
            'variance': cum_b - cum_a, 'used': self._pct(cum_a, cum_b),
            'months_to_date': len([r for r in rows if not r['future']]),
            'max': max([r['budget'] for r in rows] + [r['actual'] or 0 for r in rows] + [1]),
            'branch_note': branch_note,
            'drill': {'model': 'account.move.line',
                      'domain': base + [('date', '>=', _d(start)), ('date', '<', _d(end))],
                      'name': 'Expenses in the plan period'},
        }
