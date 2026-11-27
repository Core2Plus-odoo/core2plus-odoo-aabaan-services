/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { FmCommandCentre } from "@fm_command_centre/dashboard";

/** Budget Dashboard — "One Budget, Every Branch". Same look and helpers as
 *  the CEO Dashboard; its own data provider (fm.cc.budget.dashboard). */
export class FmBudgetDashboard extends Component {
    static template = "fm_command_centre.BudgetDashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null, error: null, loading: false,
            start: false, location: false, section: "monthly",
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("fm.cc.budget.dashboard", "get_data", [
                this.state.start, this.state.location || false,
            ]);
            this.state.data = data;
            this.state.start = data.start;
        } catch (error) {
            this.state.error = String((error && (error.data?.message || error.message)) || error);
        } finally {
            this.state.loading = false;
        }
    }

    get sectionList() {
        return [
            { key: "monthly", label: "Monthly Budget" },
            { key: "groups", label: "Where the Money Goes" },
            { key: "score", label: "Branch Scorecard" },
            { key: "team", label: "Team & Payroll" },
            { key: "actual", label: "Budget vs Actual" },
        ].map((s, i) => ({ ...s, num: i + 1 }));
    }

    selectSection(key) {
        this.state.section = key;
        const root = document.querySelector(".o_cc_root");
        if (root) root.scrollTop = 0;
    }

    showSection(key) {
        return this.state.section === "all" || this.state.section === key;
    }

    shiftPlan(step) {
        const [y, m] = this.state.start.split("-").map(Number);
        const d = new Date(y, m - 1 + 12 * step, 1);
        this.state.start = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        this.load();
    }

    onLocationChange(ev) {
        this.state.location = ev.target.value || false;
        this.load();
    }

    print() {
        window.print();
    }

    /** colour class per location, in the PDF's legend order */
    locClass(index) {
        return "o_cc_loc" + (index % 5);
    }

    grpClass(index) {
        return "o_cc_grp" + (index % 7);
    }

    /** stacked monthly columns by location, with a dashed average line */
    stackChart() {
        const d = this.state.data;
        const rows = d.monthly;
        const W = 1000, H = 280, L = 46, R = 70, T = 24, B = 30;
        const maxV = Math.max(1, ...rows.map((r) => r.total));
        const step = this.niceStep(maxV / 5);
        const top = Math.ceil(maxV / step) * step;
        const slot = (W - L - R) / Math.max(1, rows.length);
        const bw = Math.min(56, slot * 0.6);
        const y = (v) => T + (H - T - B) * (1 - v / top);
        const ticks = [];
        for (let v = 0; v <= top + 1e-6; v += step) {
            ticks.push({ y: y(v), label: this.k(v) });
        }
        const bars = rows.map((r, i) => {
            const x = L + slot * i + (slot - bw) / 2;
            let acc = 0;
            const segs = r.cells.map((v, j) => {
                const y0 = y(acc), y1 = y(acc + v);
                acc += v;
                return { y: y1, h: Math.max(0, y0 - y1), cls: this.locClass(j), v };
            });
            return { x, w: bw, cx: x + bw / 2, segs, top: y(r.total), total: this.k(r.total), label: r.short, drill: r.drill };
        });
        return { W, H, L, right: W - R, ticks, bars, base: y(0), avgY: y(d.cover.avg), avg: this.k(d.cover.avg) };
    }

    /** budget vs actual: paired columns per month */
    pairChart() {
        const a = this.state.data.actual;
        const rows = a.rows;
        const W = 1000, H = 240, L = 46, R = 10, T = 22, B = 30;
        const step = this.niceStep(a.max / 5);
        const top = Math.max(step, Math.ceil(a.max / step) * step);
        const slot = (W - L - R) / Math.max(1, rows.length);
        const bw = Math.min(26, slot * 0.32);
        const y = (v) => T + (H - T - B) * (1 - v / top);
        const ticks = [];
        for (let v = 0; v <= top + 1e-6; v += step) {
            ticks.push({ y: y(v), label: this.k(v) });
        }
        return {
            W, H, L, right: W - R, ticks, base: y(0), bw,
            bars: rows.map((r, i) => {
                const cx = L + slot * i + slot / 2;
                return {
                    label: r.label.split(" ")[0], cx, future: r.future, drill: r.drill,
                    bx: cx - bw - 2, by: y(r.budget), bh: y(0) - y(r.budget),
                    ax: cx + 2, ay: y(r.actual || 0), ah: y(0) - y(r.actual || 0),
                    over: r.actual !== null && r.actual > r.budget,
                };
            }),
        };
    }
}

// Share the CEO Dashboard's formatting, chart and drill-down helpers.
for (const name of ["k", "aed", "num", "amt", "pct", "signed", "width", "niceStep", "open", "maxOf"]) {
    FmBudgetDashboard.prototype[name] = FmCommandCentre.prototype[name];
}

registry.category("actions").add("fm_budget_dashboard", FmBudgetDashboard);
