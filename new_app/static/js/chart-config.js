/**
 * Chart Config Builder — Shared Chart.js Utilities
 *
 * Provides helper methods used by widget-specific chart builders
 * (WidgetChartBuilders[widgetName].buildConfig).
 *
 * All colors are read from CSS custom properties defined in theme.css.
 * To retheme charts, edit only theme.css — no JS changes needed.
 */
const ChartConfigBuilder = {
    // ─── CSS variable reader ──────────────────────────────────
    /**
     * Read a CSS custom property value from :root.
     * Used so all chart colors track theme.css without hardcoding.
     * Falls back to `fallback` if the var is not defined.
     */
    _cssVar(name, fallback) {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || fallback || '';
    },

    // ─── Curve-type helpers ───────────────────────────────────
    _curveProps(curveType) {
        switch (curveType) {
            case 'stepped': return { stepped: true, tension: 0 };
            case 'linear': return { stepped: false, tension: 0 };
            case 'stacked': return { stepped: false, tension: 0.4 };
            case 'smooth':
            default: return { stepped: false, tension: 0.4 };
        }
    },

    // ─── Zoom / pan defaults ──────────────────────────────────
    _zoomOptions(resetBtn) {
        return {
            pan: {
                enabled: true,
                mode: 'x',
                onPanComplete: resetBtn
                    ? () => { resetBtn.style.display = 'inline-block'; }
                    : undefined,
            },
            zoom: {
                wheel: { enabled: true, modifierKey: 'ctrl' },
                pinch: { enabled: true },
                mode: 'x',
                onZoomComplete: resetBtn
                    ? () => { resetBtn.style.display = 'inline-block'; }
                    : undefined,
            },
            limits: { x: { minRange: 2 } },
        };
    },

    // ─── Downtime annotation builder ──────────────────────────
    buildDowntimeAnnotations(downtimeEvents) {
        if (!downtimeEvents || !downtimeEvents.length) return {};
        const annotations = {};

        // Parada calculada (gap analysis) — ROJO
        const calcBg = this._cssVar('--chart-dt-bg', 'rgba(239,68,68,0.15)');
        const calcBdr = this._cssVar('--chart-dt-border', 'rgba(239,68,68,0.6)');
        const calcLc = this._cssVar('--chart-dt-label', '#fca5a5');
        const calcLb = this._cssVar('--chart-dt-label-bg', 'rgba(127,29,29,0.85)');

        // Parada registrada SIN motivo — NARANJA
        const unconfBg = this._cssVar('--chart-dt-incident-bg', 'rgba(249,115,22,0.15)');
        const unconfBdr = this._cssVar('--chart-dt-incident-border', 'rgba(249,115,22,0.6)');
        const unconfLc = this._cssVar('--chart-dt-incident-label', '#fdba74');
        const unconfLb = this._cssVar('--chart-dt-incident-label-bg', 'rgba(124,45,18,0.85)');

        // Parada registrada CON motivo — VERDE
        const confBg = this._cssVar('--chart-dt-confirmed-bg', 'rgba(34,197,94,0.15)');
        const confBdr = this._cssVar('--chart-dt-confirmed-border', 'rgba(34,197,94,0.6)');
        const confLc = this._cssVar('--chart-dt-confirmed-label', '#86efac');
        const confLb = this._cssVar('--chart-dt-confirmed-label-bg', 'rgba(20,83,45,0.85)');

        downtimeEvents.forEach((evt, i) => {
            // Leer visual_type del backend; fallback para datos sin el campo nuevo
            let vtype = evt.visual_type;
            if (!vtype) {
                if (evt.source === 'db' && evt.has_incident) vtype = 'db_confirmed';
                else if (evt.source === 'db') vtype = 'db_unconfirmed';
                else vtype = 'calculated';
            }

            let bg, bdr, lc, lb, icon;
            if (vtype === 'db_confirmed') {
                bg = confBg; bdr = confBdr; lc = confLc; lb = confLb; icon = '✓';
            } else if (vtype === 'db_unconfirmed') {
                bg = unconfBg; bdr = unconfBdr; lc = unconfLc; lb = unconfLb; icon = '⏺';
            } else {
                bg = calcBg; bdr = calcBdr; lc = calcLc; lb = calcLb; icon = '⏸';
            }

            annotations[`dt_${i}`] = {
                type: 'box',
                xMin: evt.xMin,
                xMax: Math.max(evt.xMax, evt.xMin + 0.5),
                yMin: 0,
                backgroundColor: bg,
                borderColor: bdr,
                borderWidth: 1,
                borderDash: [4, 2],
                label: {
                    display: true,
                    content: `${icon} ${evt.duration_min}min`,
                    position: 'start',
                    font: { size: 9, weight: 'bold' },
                    color: lc,
                    backgroundColor: lb,
                    padding: { top: 2, bottom: 2, left: 4, right: 4 },
                    borderRadius: 3,
                },
            };
        });
        return annotations;
    },

    // ─── Shared tooltip options ───────────────────────────────
    _tooltipDefaults() {
        return {
            backgroundColor: this._cssVar('--chart-tooltip-bg', 'rgba(2,6,23,0.95)'),
            titleFont: { size: 13, weight: '600' },
            bodyFont: { size: 12 },
            padding: 12,
            cornerRadius: 8,
            caretSize: 6,
            borderColor: 'rgba(51,65,85,0.5)',
            borderWidth: 1,
        };
    },

    /** Retrieves curve type settings for dynamic updating */
    getCurveProps(curveType) {
        return this._curveProps(curveType);
    }
};
