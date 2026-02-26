/**
 * Chart Config Builder — Chart.js Options & Data Mapping
 *
 * Separates the configuration logic from the rendering logic.
 * Exposes methods to build the configuration objects for different chart types.
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
        // Read colors from CSS vars → follows theme.css changes automatically
        const bg      = this._cssVar('--chart-dt-bg',                 'rgba(239,68,68,0.15)');
        const bdr     = this._cssVar('--chart-dt-border',             'rgba(239,68,68,0.6)');
        const lc      = this._cssVar('--chart-dt-label',              '#fca5a5');
        const lb      = this._cssVar('--chart-dt-label-bg',           'rgba(127,29,29,0.85)');
        const ibg     = this._cssVar('--chart-dt-incident-bg',        'rgba(249,115,22,0.15)');
        const ibdr    = this._cssVar('--chart-dt-incident-border',    'rgba(249,115,22,0.6)');
        const ilc     = this._cssVar('--chart-dt-incident-label',     '#fdba74');
        const ilb     = this._cssVar('--chart-dt-incident-label-bg',  'rgba(124,45,18,0.85)');
        downtimeEvents.forEach((evt, i) => {
            const incident = !!evt.has_incident;
            annotations[`dt_${i}`] = {
                type: 'box',
                xMin: evt.xMin,
                xMax: Math.max(evt.xMax, evt.xMin + 0.5),
                yMin: 0,
                backgroundColor: incident ? ibg  : bg,
                borderColor:     incident ? ibdr : bdr,
                borderWidth: 1,
                borderDash: [4, 2],
                label: {
                    display: true,
                    content: `\u23F8 ${evt.duration_min}min`,
                    position: 'start',
                    font: { size: 9, weight: 'bold' },
                    color: incident ? ilc : lc,
                    backgroundColor: incident ? ilb : lb,
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

    // ─── Config Builders ──────────────────────────────────────
    /**
     * Build config for the production timeline chart.
     *
     * @param {Object}  data        Widget data object from API.
     * @param {Element} resetBtn    "Reset Zoom" button element (or null).
     * @param {boolean} isMultiLine Multi-line comparison mode.
     * @param {string}  mode        'line' (default) | 'bar' — chart type toggle.
     *
     * Both modes share: aggregation labels, dataset colors, class-detail tooltip,
     * downtime annotations, zoom/pan, and scale styling.
     */
    buildLineConfig(data, resetBtn, isMultiLine, mode) {
        const asBar     = mode === 'bar';
        const curveType = data.curve_type || 'smooth';
        const curve     = this._curveProps(curveType);
        const stacked   = curveType === 'stacked';
        const classDetails = data.class_details || {};
        const multi     = (data.datasets || []).length > 1;
        const dtEvts    = data.downtime_events || [];
        const showDt    = data.show_downtime !== false;
        const dtAnnot   = (isMultiLine || !showDt) ? {} : this.buildDowntimeAnnotations(dtEvts);

        // Dataset colors: use CSS vars for first 5 datasets, fallback to hardcoded
        const lineColors = [
            [this._cssVar('--chart-line-1', '#22c55e'), this._cssVar('--chart-line-bg-1', 'rgba(34,197,94,0.08)')],
            [this._cssVar('--chart-line-2', '#38bdf8'), this._cssVar('--chart-line-bg-2', 'rgba(56,189,248,0.08)')],
            [this._cssVar('--chart-line-3', '#fbbf24'), this._cssVar('--chart-line-bg-3', 'rgba(251,191,36,0.08)')],
            [this._cssVar('--chart-line-4', '#f87171'), this._cssVar('--chart-line-bg-4', 'rgba(248,113,113,0.08)')],
            [this._cssVar('--chart-line-5', '#a78bfa'), this._cssVar('--chart-line-bg-5', 'rgba(167,139,250,0.08)')],
        ];

        const gridColor = this._cssVar('--chart-grid', 'rgba(148,163,184,0.08)');
        const tickColor = this._cssVar('--chart-tick', '#94a3b8');

        const datasets = (data.datasets || []).map((ds, i) => {
            const [lc, bg] = lineColors[i % lineColors.length];
            const borderColor = ds.borderColor || lc;
            const bgColor    = ds.backgroundColor || bg;

            if (asBar) {
                // Bar mode: solid fill with slight transparency, rounded tops
                return {
                    label:           ds.label || 'Producción',
                    data:            ds.data  || [],
                    backgroundColor: borderColor.startsWith('#')
                        ? borderColor + 'CC'   // add ~80% opacity to hex color
                        : borderColor,
                    borderColor:     borderColor,
                    borderWidth:     1,
                    borderRadius:    4,
                    borderSkipped:   false,
                };
            }
            return {
                label:           ds.label || 'Producción',
                data:            ds.data  || [],
                borderColor,
                backgroundColor: stacked ? bgColor : (ds.fill !== undefined && ds.fill ? bgColor : bgColor),
                fill:            stacked ? 'origin' : (ds.fill !== undefined ? ds.fill : false),
                tension:         curve.tension,
                stepped:         curve.stepped,
                pointRadius:     2,
                pointHoverRadius: 6,
                borderWidth:     2,
            };
        });

        // Shared tooltip callback — class breakdown in body
        const tooltipCallbacks = {
            afterBody(items) {
                if (!items.length) return '';
                const lbl = items[0].label;
                const detail = classDetails[lbl];
                if (!detail) return '';
                const lines = ['\u2500\u2500\u2500 Clases \u2500\u2500\u2500'];
                Object.entries(detail)
                    .sort((a, b) => b[1] - a[1])
                    .forEach(([cls, cnt]) => lines.push(`  ${cls}: ${cnt}`));
                return lines;
            },
        };

        return {
            type: asBar ? 'bar' : 'line',
            data: {
                labels:   data.labels || [],
                datasets,
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                interaction: asBar
                    ? { mode: 'index', intersect: false }
                    : { mode: 'nearest', intersect: true },
                plugins: {
                    legend: {
                        display: multi,
                        position: 'top',
                        labels: {
                            color:          tickColor,
                            usePointStyle:  true,
                            pointStyle:     asBar ? 'rect' : 'circle',
                            padding:        16,
                            font:           { size: 11 },
                        },
                    },
                    tooltip: {
                        ...this._tooltipDefaults(),
                        callbacks: tooltipCallbacks,
                    },
                    annotation: Object.keys(dtAnnot).length > 0 ? { annotations: dtAnnot } : false,
                    zoom: this._zoomOptions(resetBtn),
                },
                scales: {
                    x: {
                        stacked: asBar ? false : stacked,
                        grid:    { color: gridColor, display: !asBar },
                        ticks:   { color: tickColor, maxTicksLimit: 14, font: { size: 10 } },
                    },
                    y: {
                        stacked: asBar ? false : stacked,
                        grid:    { color: gridColor },
                        ticks:   { color: tickColor, font: { size: 10 } },
                        beginAtZero: true,
                    },
                },
            },
        };
    },

    buildBarConfig(data, resetBtn) {
        const multi = (data.datasets || []).length > 1;
        const gridColor = this._cssVar('--chart-grid', 'rgba(148,163,184,0.08)');
        const tickColor = this._cssVar('--chart-tick', '#94a3b8');
        return {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: (data.datasets || []).map(ds => ({
                    label: ds.label || '',
                    data: ds.data || [],
                    backgroundColor: ds.backgroundColor || '#22c55e',
                    borderRadius: 4,
                    borderSkipped: false,
                })),
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: multi,
                        position: 'top',
                        labels: { color: tickColor, usePointStyle: true, pointStyle: 'rect', padding: 16, font: { size: 11 } },
                    },
                    tooltip: this._tooltipDefaults(),
                    zoom: multi ? this._zoomOptions(resetBtn) : false,
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tickColor, font: { size: 10 }, maxTicksLimit: 14 } },
                    y: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 10 } }, beginAtZero: true },
                },
            },
        };
    },

    buildPieConfig(data) {
        return {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: (data.datasets || []).map(ds => ({
                    data: ds.data || [],
                    backgroundColor: ds.backgroundColor || ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'],
                    borderWidth: 2,
                    borderColor: '#0F172A',
                })),
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { color: '#94a3b8', padding: 12, font: { size: 11 } } },
                    tooltip: this._tooltipDefaults(),
                },
            },
        };
    },

    buildScatterConfig(data, resetBtn, isMultiLine) {
        return {
            type: 'scatter',
            data: {
                datasets: (data.datasets || []).map(ds => ({
                    label: ds.label || '',
                    data: ds.data || [],
                    backgroundColor: ds.backgroundColor || '#22c55e',
                    borderColor: ds.borderColor || '#22c55e',
                    pointRadius: ds.pointRadius || 6,
                    pointHoverRadius: 9,
                })),
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'linear', position: 'bottom',
                        title: { display: true, text: 'Hora del Día (0-24)', color: '#94a3b8' },
                        min: 0, max: 24,
                        grid: { color: 'rgba(148,163,184,0.08)' },
                        ticks: { color: '#94a3b8', stepSize: 2 },
                    },
                    y: {
                        title: { display: true, text: 'Duración (min)', color: '#94a3b8' },
                        beginAtZero: true,
                        grid: { color: 'rgba(148,163,184,0.08)' },
                        ticks: { color: '#94a3b8' },
                    },
                },
                plugins: {
                    legend: { display: true, position: 'top', labels: { color: '#94a3b8', usePointStyle: true, padding: 16, font: { size: 11 } } },
                    tooltip: {
                        ...this._tooltipDefaults(),
                        callbacks: {
                            label(ctx) {
                                const p = ctx.raw;
                                const h = Math.floor(p.x);
                                const m = Math.round((p.x - h) * 60);
                                let lbl = `${h}:${String(m).padStart(2, '0')} \u2014 ${p.y} min`;
                                if (p.tooltip) lbl += ` | ${p.tooltip}`;
                                return lbl;
                            },
                        },
                    },
                    zoom: this._zoomOptions(resetBtn),
                },
            },
        };
    },

    /** Dispatches to the correct builder. */
    getConfig(chartType, data, resetBtn, isMultiLine, mode) {
        switch (chartType) {
            case 'line_chart': return this.buildLineConfig(data, resetBtn, isMultiLine, mode);
            case 'bar_chart': return this.buildBarConfig(data, resetBtn);
            case 'comparison_bar': return this.buildBarConfig(data, resetBtn);
            case 'pie_chart': return this.buildPieConfig(data);
            case 'scatter_chart': return this.buildScatterConfig(data, resetBtn, isMultiLine);
            default: return null;
        }
    },

    /** Retrieves curve type settings for dynamic updating */
    getCurveProps(curveType) {
        return this._curveProps(curveType);
    }
};
