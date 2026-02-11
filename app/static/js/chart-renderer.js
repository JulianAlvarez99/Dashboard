/**
 * Chart Renderer - Chart.js configuration and rendering
 *
 * Centralizes all Chart.js chart creation logic.
 * Supports:
 *  - Per-product coloured datasets on line charts
 *  - Curve type switching (stepped / smooth / linear / stacked)
 *  - Rich tooltips showing class breakdown per time bucket
 *  - Zoom & pan via chartjs-plugin-zoom
 *  - Time-series comparison bar charts
 */

const ChartRenderer = {

    // ─── Curve-type helpers ──────────────────────────────────────

    /**
     * Map a curve_type string to the Chart.js line dataset properties.
     */
    _curveProps(curveType) {
        switch (curveType) {
            case 'stepped':
                return { stepped: true, tension: 0 };
            case 'linear':
                return { stepped: false, tension: 0 };
            case 'stacked':
                return { stepped: false, tension: 0.4 };
            case 'smooth':
            default:
                return { stepped: false, tension: 0.4 };
        }
    },

    // ─── Zoom / pan defaults ─────────────────────────────────────

    /**
     * Build zoom/pan plugin options.
     * @param {HTMLElement|null} resetBtn - optional reset-zoom button to show/hide
     */
    _zoomOptions(resetBtn) {
        return {
            pan: {
                enabled: true,
                mode: 'x',
                modifierKey: null,          // Regular drag → pan along timeline
                onPanComplete: resetBtn ? () => { resetBtn.style.display = 'inline-block'; } : undefined,
            },
            zoom: {
                wheel: { enabled: true, modifierKey: 'ctrl' },   // Ctrl+wheel → zoom
                pinch: { enabled: true },
                drag: {
                    enabled: true,
                    modifierKey: 'ctrl',    // Ctrl+drag → area selection zoom
                    backgroundColor: 'rgba(59,130,246,0.15)',
                    borderColor: '#3b82f6',
                    borderWidth: 1,
                },
                mode: 'x',
                onZoomComplete: resetBtn ? () => { resetBtn.style.display = 'inline-block'; } : undefined,
            },
            limits: {
                x: { minRange: 2 },
            },
        };
    },

    // ─── Downtime annotation builder ────────────────────────────

    /**
     * Build Chart.js annotation plugin config from downtime_events.
     * Each event becomes a translucent red box spanning its time range.
     */
    _buildDowntimeAnnotations(downtimeEvents) {
        if (!downtimeEvents || !downtimeEvents.length) return {};

        const annotations = {};
        downtimeEvents.forEach((evt, i) => {
            // Orange for registered incidents, red for gap-detected stops
            const incident = !!evt.has_incident;
            const bg   = incident ? 'rgba(249,115,22,0.15)' : 'rgba(239,68,68,0.15)';
            const bdr  = incident ? 'rgba(249,115,22,0.6)'  : 'rgba(239,68,68,0.6)';
            const lclr = incident ? '#fdba74' : '#fca5a5';
            const lbg  = incident ? 'rgba(124,45,18,0.85)'  : 'rgba(127,29,29,0.85)';

            annotations[`downtime_${i}`] = {
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
                    content: `⏸ ${evt.duration_min}min`,
                    position: 'start',
                    font: { size: 9, weight: 'bold' },
                    color: lclr,
                    backgroundColor: lbg,
                    padding: { top: 2, bottom: 2, left: 4, right: 4 },
                    borderRadius: 3,
                },
            };
        });
        return annotations;
    },

    // ─── Line Chart Config Builder ───────────────────────────────

    buildLineConfig(data, resetBtn, isMultiLine) {
        const curveType = data.curve_type || 'smooth';
        const curveProps = this._curveProps(curveType);
        const stacked = curveType === 'stacked';
        const classDetails = data.class_details || {};
        const multiDataset = (data.datasets || []).length > 1;
        const downtimeEvents = data.downtime_events || [];
        // Hide downtime annotations in multi-line mode
        const downtimeAnnotations = isMultiLine ? {} : this._buildDowntimeAnnotations(downtimeEvents);

        return {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: (data.datasets || []).map(ds => ({
                    label: ds.label || 'Producción',
                    data: ds.data || [],
                    borderColor: ds.borderColor || '#3b82f6',
                    backgroundColor: ds.backgroundColor || 'rgba(59,130,246,0.1)',
                    fill: stacked ? 'origin' : (ds.fill !== undefined ? ds.fill : false),
                    tension: curveProps.tension,
                    stepped: curveProps.stepped,
                    pointRadius: 2,
                    pointHoverRadius: 6,
                    borderWidth: 2,
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'nearest', intersect: true },
                plugins: {
                    legend: {
                        display: multiDataset,
                        position: 'top',
                        labels: {
                            color: '#94a3b8',
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 16,
                            font: { size: 11 },
                        },
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.95)',
                        titleFont: { size: 13, weight: '600' },
                        bodyFont: { size: 12 },
                        padding: 12,
                        cornerRadius: 8,
                        caretSize: 6,
                        callbacks: {
                            afterBody(tooltipItems) {
                                if (!tooltipItems.length) return '';
                                const label = tooltipItems[0].label;
                                const detail = classDetails[label];
                                if (!detail) return '';
                                const lines = ['─── Clases ───'];
                                Object.entries(detail)
                                    .sort((a, b) => b[1] - a[1])
                                    .forEach(([cls, cnt]) => {
                                        lines.push(`  ${cls}: ${cnt}`);
                                    });
                                return lines;
                            },
                        },
                    },
                    annotation: Object.keys(downtimeAnnotations).length > 0
                        ? { annotations: downtimeAnnotations }
                        : false,
                    zoom: this._zoomOptions(resetBtn),
                },
                scales: {
                    x: {
                        stacked,
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        ticks: { color: '#94a3b8', maxTicksLimit: 14, font: { size: 10 } },
                    },
                    y: {
                        stacked,
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        ticks: { color: '#94a3b8', font: { size: 10 } },
                        beginAtZero: true,
                    },
                },
            },
        };
    },

    // ─── Bar Chart Config Builder ────────────────────────────────

    buildBarConfig(data, resetBtn) {
        const isTimeSeries = (data.datasets || []).length > 1;
        return {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: (data.datasets || []).map(ds => ({
                    label: ds.label || '',
                    data: ds.data || [],
                    backgroundColor: ds.backgroundColor || '#3b82f6',
                    borderRadius: 4,
                    borderSkipped: false,
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: isTimeSeries,
                        position: 'top',
                        labels: {
                            color: '#94a3b8',
                            usePointStyle: true,
                            pointStyle: 'rect',
                            padding: 16,
                            font: { size: 11 },
                        },
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.95)',
                        titleFont: { size: 13, weight: '600' },
                        bodyFont: { size: 12 },
                        padding: 12,
                        cornerRadius: 8,
                    },
                    zoom: isTimeSeries ? this._zoomOptions(resetBtn) : false,
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#94a3b8', font: { size: 10 }, maxTicksLimit: 14 },
                    },
                    y: {
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        ticks: { color: '#94a3b8', font: { size: 10 } },
                        beginAtZero: true,
                    },
                },
            },
        };
    },

    // ─── Pie / Doughnut Config Builder ───────────────────────────

    buildPieConfig(data, _resetBtn) {
        return {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: (data.datasets || []).map(ds => ({
                    data: ds.data || [],
                    backgroundColor: ds.backgroundColor || ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444'],
                    borderWidth: 2,
                    borderColor: '#1e293b',
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { color: '#94a3b8', padding: 12, font: { size: 11 } },
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.95)',
                        titleFont: { size: 13, weight: '600' },
                        bodyFont: { size: 12 },
                        padding: 12,
                        cornerRadius: 8,
                    },
                },
            },
        };
    },

    // ─── Scatter Chart Config Builder ───────────────────────────

    buildScatterConfig(data, resetBtn, isMultiLine) {
        return {
            type: 'scatter',
            data: {
                datasets: (data.datasets || []).map(ds => ({
                    label: ds.label || '',
                    data: ds.data || [],
                    backgroundColor: ds.backgroundColor || '#3b82f6',
                    borderColor: ds.borderColor || '#3b82f6',
                    pointRadius: ds.pointRadius || 6,
                    pointHoverRadius: 9,
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: { display: true, text: 'Hora del Día (0-24)', color: '#94a3b8' },
                        min: 0, max: 24,
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        ticks: { color: '#94a3b8', stepSize: 2 },
                    },
                    y: {
                        title: { display: true, text: 'Duración (min)', color: '#94a3b8' },
                        beginAtZero: true,
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        ticks: { color: '#94a3b8' },
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: { color: '#94a3b8', usePointStyle: true, padding: 16, font: { size: 11 } },
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.95)',
                        titleFont: { size: 13, weight: '600' },
                        bodyFont: { size: 12 },
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label(ctx) {
                                const p = ctx.raw;
                                const h = Math.floor(p.x);
                                const m = Math.round((p.x - h) * 60);
                                let lbl = `${h}:${String(m).padStart(2,'0')} — ${p.y} min`;
                                if (p.tooltip) lbl += ` | ${p.tooltip}`;
                                return lbl;
                            }
                        }
                    },
                    zoom: this._zoomOptions(resetBtn),
                },
            },
            // Mark as multi-line so render() can hide it
            _isMultiLine: isMultiLine,
        };
    },

    // ─── Builder map ─────────────────────────────────────────────

    _configBuilders: {
        'line_chart': 'buildLineConfig',
        'bar_chart': 'buildBarConfig',
        'comparison_bar': 'buildBarConfig',
        'pie_chart': 'buildPieConfig',
        'scatter_chart': 'buildScatterConfig',
    },

    // ─── Render / destroy ────────────────────────────────────────

    /**
     * Render (or re-render) a chart for the given widget data.
     * Handles destroying any previous chart on the same canvas.
     *
     * @param {Object} widgetData - The widget data from the API
     * @param {Object} chartInstances - Map of canvasId → Chart instance
     * @param {boolean} isMultiLine - Whether multi-line mode is active
     * @param {number} _attempt - Internal retry counter
     * @returns {Chart|null} The created Chart instance, or null
     */
    render(widgetData, chartInstances, isMultiLine, _attempt) {
        if (!widgetData || !widgetData.data) return null;

        const canvasId = `chart-${widgetData.widget_id}`;
        const canvas = document.getElementById(canvasId);

        // If canvas not yet in DOM (or still hidden), retry up to 10 times
        if (!canvas || canvas.offsetWidth === 0) {
            const attempt = (_attempt || 0) + 1;
            if (attempt <= 10) {
                setTimeout(() => this.render(widgetData, chartInstances, isMultiLine, attempt), 50);
            }
            return null;
        }

        // Destroy existing chart on this canvas
        if (chartInstances[canvasId]) {
            chartInstances[canvasId].destroy();
            delete chartInstances[canvasId];
        }

        const builderName = this._configBuilders[widgetData.widget_type];
        if (!builderName) return null;

        // Create zoom toolbar BEFORE chart so callbacks are wired into config
        const resetBtn = this._createZoomToolbar(canvas, widgetData.widget_type);

        const config = this[builderName](widgetData.data, resetBtn, isMultiLine);
        const chart = new Chart(canvas.getContext('2d'), config);
        chartInstances[canvasId] = chart;

        // Wire the reset button click to this chart instance
        if (resetBtn) {
            resetBtn.onclick = () => {
                chart.resetZoom();
                resetBtn.style.display = 'none';
            };

            // Native dblclick event listener to reset zoom (onDblClick is not a Chart.js option)
            canvas.addEventListener('dblclick', () => {
                chart.resetZoom();
                resetBtn.style.display = 'none';
            });
        }

        return chart;
    },

    /**
     * Create a zoom toolbar with hint text and a reset button above the canvas.
     * Returns the reset button element (or null if not a zoomable chart type).
     */
    _createZoomToolbar(canvas, widgetType) {
        const zoomableTypes = ['line_chart', 'bar_chart', 'comparison_bar', 'scatter_chart'];
        if (!zoomableTypes.includes(widgetType)) return null;

        const wrapper = canvas.closest('.widget-chart-wrap') || canvas.parentElement;
        if (!wrapper) return null;

        // Remove any existing toolbar for this chart
        const existingBar = wrapper.querySelector('.chart-zoom-toolbar');
        if (existingBar) existingBar.remove();

        const toolbar = document.createElement('div');
        toolbar.className = 'chart-zoom-toolbar';
        toolbar.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:4px 8px 2px;font-size:11px;color:#64748b;';

        // Hint text
        const hint = document.createElement('span');
        hint.textContent = 'Arrastrar: mover · Ctrl+rueda: zoom · Ctrl+arrastrar: seleccionar zona · Doble-clic: resetear';
        hint.style.cssText = 'opacity:0.7;';

        // Reset button (hidden until zoomed)
        const btn = document.createElement('button');
        btn.textContent = '↺ Reset Zoom';
        btn.style.cssText = 'display:none;padding:2px 10px;border-radius:4px;background:#334155;color:#e2e8f0;cursor:pointer;font-size:11px;border:1px solid #475569;transition:background .15s;';
        btn.onmouseenter = () => { btn.style.background = '#475569'; };
        btn.onmouseleave = () => { btn.style.background = '#334155'; };

        toolbar.appendChild(hint);
        toolbar.appendChild(btn);
        wrapper.insertBefore(toolbar, canvas);

        return btn;
    },

    /**
     * Destroy all chart instances
     * @param {Object} chartInstances - Map of canvasId → Chart instance
     */
    destroyAll(chartInstances) {
        Object.keys(chartInstances).forEach(key => {
            if (chartInstances[key]) {
                chartInstances[key].destroy();
            }
        });
        Object.keys(chartInstances).forEach(k => delete chartInstances[k]);
    },
};
