/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SERVICE_ICONS = {
    pest: "🐞", termite: "🐜", tank: "💧", fumigation: "🧪", villa: "🏡",
    ac: "❄️", flat: "🏢", sofa: "🛋️", carpet: "🟥", painting: "🖌️",
    mattress: "🛏️", landscaping: "🌿", handyman: "🔧", electrical: "🔌",
    tile: "🔲", plumbing: "🪠", cleaning: "🧽", lab: "🧫", project: "🏗️", other: "📦",
};

export class FmCommandCentre extends Component {
    static template = "fm_command_centre.Dashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null,
            error: null,
            loading: false,
            month: false,
            includeDraft: true,
            // Which numbered section is on screen; the cover always is.
            section: "all",
            service: false,
            branch: false,
        });
        onWillStart(() => this.load());
    }

    /** The 8-section variant (client PDF "AMC vs Cash", 9 pages): the same
     *  dashboard without Revenue by Service and Services by Emirate. */
    get isCompact() {
        return (this.props.action?.params?.variant || "") === "compact";
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("fm.command.centre", "get_data", [
                this.state.month,
                this.state.includeDraft,
                this.isCompact ? "compact" : "full",
                this.state.service || false,
                this.state.branch || false,
            ]);
            this.state.data = data;
            this.state.month = data.month;
        } catch (error) {
            this.state.error = String((error && (error.data?.message || error.message)) || error);
        } finally {
            this.state.loading = false;
        }
    }

    // ---- sections ------------------------------------------------------

    get sectionList() {
        const all = [
            { key: "versus", label: "AMC vs Cash Sales" },
            { key: "amc", label: "AMC Department" },
            { key: "cash", label: "Cash Sales" },
            { key: "scorecard", label: "Branch Scorecard" },
            { key: "services", label: "Revenue by Service", full: true },
            { key: "emirate", label: "Services by Emirate", full: true },
            { key: "credit", label: "Credit Recovery" },
            { key: "sales", label: "Sales Team" },
            { key: "expenses", label: "Expenses & Margin" },
            { key: "bank", label: "Cash & Bank" },
        ];
        return all
            .filter((s) => !(s.full && this.isCompact))
            .map((s, i) => ({ ...s, num: i + 1 }));
    }

    selectSection(key) {
        this.state.section = key;
        const root = document.querySelector(".o_cc_root");
        if (root) {
            root.scrollTop = 0;
        }
    }

    showSection(key) {
        return this.state.section === "all" || this.state.section === key;
    }

    // ---- toolbar -------------------------------------------------------

    shiftMonth(step) {
        const [y, m] = (this.state.month || this.state.data.month).split("-").map(Number);
        const d = new Date(y, m - 1 + step, 1);
        this.state.month = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        this.load();
    }

    onMonthInput(ev) {
        if (ev.target.value) {
            this.state.month = ev.target.value;
            this.load();
        }
    }

    onBranchChange(ev) {
        this.state.branch = parseInt(ev.target.value, 10) || false;
        this.load();
    }

    onServiceChange(ev) {
        this.state.service = ev.target.value || false;
        this.load();
    }

    toggleDraft() {
        this.state.includeDraft = !this.state.includeDraft;
        this.load();
    }

    print() {
        window.print();
    }

    // ---- formatting ----------------------------------------------------

    k(value) {
        const v = value || 0;
        const a = Math.abs(v);
        if (a >= 1e6) return (v / 1e6).toFixed(2) + "M";
        if (a >= 1e3) return (v / 1e3).toFixed(1) + "K";
        return Math.round(v).toLocaleString();
    }

    aed(value) {
        return "AED " + this.k(value);
    }

    num(value) {
        return Math.round(value || 0).toLocaleString();
    }

    amt(value) {
        return value === null || value === undefined ? "—" : "AED " + Math.round(value).toLocaleString();
    }

    pct(value, digits = 0) {
        return value === null || value === undefined ? "—" : Number(value).toFixed(digits) + "%";
    }

    signed(value) {
        const v = value || 0;
        return (v > 0 ? "+" : v < 0 ? "−" : "") + this.k(Math.abs(v));
    }

    delta(value) {
        if (value === null || value === undefined) return "";
        return (value > 0 ? "+" : value < 0 ? "−" : "") + Math.abs(value).toFixed(1) + "%";
    }

    ach(value) {
        if (value === null || value === undefined) return "o_cc_muted";
        if (value >= 100) return "o_cc_good";
        if (value >= 90) return "o_cc_warn";
        return "o_cc_bad";
    }

    maxOf(items, key) {
        return Math.max(0, ...(items || []).map((i) => i[key] || 0));
    }

    icon(key) {
        return SERVICE_ICONS[key] || "📦";
    }

    width(value, max) {
        if (!max || !value || value <= 0) return 0;
        return Math.max(0.6, Math.min(100, (100 * value) / max));
    }

    // ---- charts --------------------------------------------------------

    /** 12-month AMC vs cash line chart, in SVG user units. */
    lineChart() {
        const months = this.state.data.versus.months;
        const W = 1000, H = 260, L = 46, R = 90, T = 16, B = 30;
        const maxV = Math.max(1, ...months.map((m) => Math.max(m.amc, m.cash)));
        const step = this.niceStep(maxV / 5);
        const top = Math.ceil(maxV / step) * step;
        const x = (i) => L + (i * (W - L - R)) / (months.length - 1);
        const y = (v) => T + (H - T - B) * (1 - v / top);
        const path = (key) => months.map((m, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(m[key]).toFixed(1)}`).join(" ");
        const ticks = [];
        for (let v = 0; v <= top + 1e-6; v += step) {
            ticks.push({ y: y(v), label: this.k(v) });
        }
        const last = months.length - 1;
        let amcY = y(months[last].amc), cashY = y(months[last].cash);
        if (Math.abs(amcY - cashY) < 34) {
            if (amcY <= cashY) { cashY = amcY + 34; } else { amcY = cashY + 34; }
        }
        return {
            W, H, ticks, L, R,
            right: W - R,
            amcPath: path("amc"),
            cashPath: path("cash"),
            labels: months.map((m, i) => ({ x: x(i), label: m.label, last: i === last })),
            amcDot: { x: x(last), y: y(months[last].amc) },
            cashDot: { x: x(last), y: y(months[last].cash) },
            amcLabelY: amcY, cashLabelY: cashY,
            amcLast: this.k(months[last].amc),
            cashLast: this.k(months[last].cash),
        };
    }

    /** New contracts vs renewals, grouped columns. */
    columnChart() {
        const months = this.state.data.amc.chart;
        const W = 1000, H = 230, L = 36, R = 10, T = 22, B = 30;
        const maxV = Math.max(1, ...months.map((m) => Math.max(m.new, m.renewal)));
        const step = this.niceStep(maxV / 5) || 1;
        const top = Math.max(step, Math.ceil(maxV / step) * step);
        const slot = (W - L - R) / months.length;
        const bw = Math.min(30, slot * 0.34);
        const y = (v) => T + (H - T - B) * (1 - v / top);
        const ticks = [];
        for (let v = 0; v <= top + 1e-6; v += step) {
            ticks.push({ y: y(v), label: Math.round(v) });
        }
        const last = months.length - 1;
        return {
            W, H, L, right: W - R, ticks, base: y(0), bw,
            bars: months.map((m, i) => {
                const cx = L + slot * i + slot / 2;
                return {
                    label: m.label, last: i === last, cx,
                    nx: cx - bw - 2, ny: y(m.new), nh: y(0) - y(m.new), n: m.new,
                    rx: cx + 2, ry: y(m.renewal), rh: y(0) - y(m.renewal), r: m.renewal,
                };
            }),
        };
    }

    niceStep(raw) {
        if (raw <= 0) return 1;
        const p = Math.pow(10, Math.floor(Math.log10(raw)));
        const n = raw / p;
        return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
    }

    // ---- drill-down ----------------------------------------------------

    open(drill) {
        if (!drill || !drill.model) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: drill.name || "Details",
            res_model: drill.model,
            domain: drill.domain || [],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openPartner(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openConfig(xmlid) {
        this.action.doAction(xmlid);
    }
}

registry.category("actions").add("fm_command_centre", FmCommandCentre);
