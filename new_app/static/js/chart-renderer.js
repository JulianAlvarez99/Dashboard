/**
 * Chart Renderer — Chart.js configuration and rendering
 *
 * Centralizes all Chart.js chart creation logic for the new_app.
 * Ported from app/static/js/chart-renderer.js with the same
 * feature set:
 *
 *   - Per-product coloured datasets on line charts
 *   - Curve type switching (stepped / smooth / linear / stacked)
 *   - Rich tooltips showing class breakdown per time bucket
 *   - Zoom & pan via chartjs-plugin-zoom
 *   - Downtime annotation boxes via chartjs-plugin-annotation
 *   - Time-series comparison bar charts
 *   - Scatter charts for downtime visualisation
 *
 * Usage:
 *   ChartRenderer.render(widgetData, chartInstances, isMultiLine);
 *   ChartRenderer.destroyAll(chartInstances);
 */

const ChartRenderer = {

  // ─── Curve-type helpers ───────────────────────────────────

  /** Map curve_type string → Chart.js line dataset properties. */
  _curveProps(curveType) {
    switch (curveType) {
      case 'stepped': return { stepped: true, tension: 0 };
      case 'linear':  return { stepped: false, tension: 0 };
      case 'stacked': return { stepped: false, tension: 0.4 };
      case 'smooth':
      default:        return { stepped: false, tension: 0.4 };
    }
  },

  // ─── Zoom / pan defaults ──────────────────────────────────

  /** Build zoom/pan plugin options. */
  _zoomOptions(resetBtn) {
    return {
      pan: {
        enabled: true,
        mode: 'x',
        modifierKey: null,
        onPanComplete: resetBtn
          ? () => { resetBtn.style.display = 'inline-block'; }
          : undefined,
      },
      zoom: {
        wheel: { enabled: true, modifierKey: 'ctrl' },
        pinch: { enabled: true },
        drag: {
          enabled: true,
          modifierKey: 'ctrl',
          backgroundColor: 'rgba(34,197,94,0.10)',
          borderColor: '#22c55e',
          borderWidth: 1,
        },
        mode: 'x',
        onZoomComplete: resetBtn
          ? () => { resetBtn.style.display = 'inline-block'; }
          : undefined,
      },
      limits: { x: { minRange: 2 } },
    };
  },

  // ─── Downtime annotation builder ──────────────────────────

  /** Build annotation plugin config from downtime_events array. */
  _buildDowntimeAnnotations(downtimeEvents) {
    if (!downtimeEvents || !downtimeEvents.length) return {};
    const annotations = {};
    downtimeEvents.forEach((evt, i) => {
      const incident = !!evt.has_incident;
      const bg  = incident ? 'rgba(249,115,22,0.15)' : 'rgba(239,68,68,0.15)';
      const bdr = incident ? 'rgba(249,115,22,0.6)'  : 'rgba(239,68,68,0.6)';
      const lc  = incident ? '#fdba74' : '#fca5a5';
      const lb  = incident ? 'rgba(124,45,18,0.85)' : 'rgba(127,29,29,0.85)';
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
          content: `\u23F8 ${evt.duration_min}min`,
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
      backgroundColor: 'rgba(2,6,23,0.95)',
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

  buildLineConfig(data, resetBtn, isMultiLine) {
    const curveType = data.curve_type || 'smooth';
    const curve = this._curveProps(curveType);
    const stacked = curveType === 'stacked';
    const classDetails = data.class_details || {};
    const multi = (data.datasets || []).length > 1;
    const dtEvts = data.downtime_events || [];
    const dtAnnot = isMultiLine ? {} : this._buildDowntimeAnnotations(dtEvts);

    return {
      type: 'line',
      data: {
        labels: data.labels || [],
        datasets: (data.datasets || []).map(ds => ({
          label: ds.label || 'Producción',
          data: ds.data || [],
          borderColor: ds.borderColor || '#22c55e',
          backgroundColor: ds.backgroundColor || 'rgba(34,197,94,0.08)',
          fill: stacked ? 'origin' : (ds.fill !== undefined ? ds.fill : false),
          tension: curve.tension,
          stepped: curve.stepped,
          pointRadius: 2,
          pointHoverRadius: 6,
          borderWidth: 2,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'nearest', intersect: true },
        plugins: {
          legend: {
            display: multi,
            position: 'top',
            labels: { color: '#94a3b8', usePointStyle: true, pointStyle: 'circle', padding: 16, font: { size: 11 } },
          },
          tooltip: {
            ...this._tooltipDefaults(),
            callbacks: {
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
            },
          },
          annotation: Object.keys(dtAnnot).length > 0 ? { annotations: dtAnnot } : false,
          zoom: this._zoomOptions(resetBtn),
        },
        scales: {
          x: { stacked, grid: { color: 'rgba(148,163,184,0.08)' }, ticks: { color: '#94a3b8', maxTicksLimit: 14, font: { size: 10 } } },
          y: { stacked, grid: { color: 'rgba(148,163,184,0.08)' }, ticks: { color: '#94a3b8', font: { size: 10 } }, beginAtZero: true },
        },
      },
    };
  },

  buildBarConfig(data, resetBtn) {
    const multi = (data.datasets || []).length > 1;
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
            labels: { color: '#94a3b8', usePointStyle: true, pointStyle: 'rect', padding: 16, font: { size: 11 } },
          },
          tooltip: this._tooltipDefaults(),
          zoom: multi ? this._zoomOptions(resetBtn) : false,
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 }, maxTicksLimit: 14 } },
          y: { grid: { color: 'rgba(148,163,184,0.08)' }, ticks: { color: '#94a3b8', font: { size: 10 } }, beginAtZero: true },
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

  // ─── Builder map ──────────────────────────────────────────

  _configBuilders: {
    'line_chart':      'buildLineConfig',
    'bar_chart':       'buildBarConfig',
    'comparison_bar':  'buildBarConfig',
    'pie_chart':       'buildPieConfig',
    'scatter_chart':   'buildScatterConfig',
  },

  // ─── Render / destroy ─────────────────────────────────────

  /**
   * Render (or re-render) a chart for the given widget data.
   *
   * @param {string}  chartType      - Chart type key (line_chart, bar_chart, etc.)
   * @param {Object}  widgetData     - The widget data from the API
   * @param {Object}  chartInstances - Map of canvasId → Chart instance
   * @param {boolean} isMultiLine    - Whether multi-line mode is active
   * @param {number}  _attempt       - Internal retry counter
   * @returns {Chart|null}
   */
  render(chartType, widgetData, chartInstances, isMultiLine, _attempt) {
    if (!widgetData || !widgetData.data) return null;

    const canvasId = `chart-${widgetData.widget_id}`;
    const canvas = document.getElementById(canvasId);

    // Retry up to 10 times if canvas not yet in DOM
    if (!canvas || canvas.offsetWidth === 0) {
      const attempt = (_attempt || 0) + 1;
      if (attempt <= 10) {
        setTimeout(() => this.render(chartType, widgetData, chartInstances, isMultiLine, attempt), 60);
      }
      return null;
    }

    // Destroy existing chart on this canvas
    if (chartInstances[canvasId]) {
      chartInstances[canvasId].destroy();
      delete chartInstances[canvasId];
    }

    const builderName = this._configBuilders[chartType];
    if (!builderName) return null;

    const resetBtn = this._createZoomToolbar(canvas, chartType);
    const config = this[builderName](widgetData.data, resetBtn, isMultiLine);
    const chart = new Chart(canvas.getContext('2d'), config);
    chartInstances[canvasId] = chart;

    // Wire reset button
    if (resetBtn) {
      resetBtn.onclick = () => { chart.resetZoom(); resetBtn.style.display = 'none'; };
      canvas.addEventListener('dblclick', () => { chart.resetZoom(); resetBtn.style.display = 'none'; });
    }

    return chart;
  },

  /** Create zoom toolbar above the canvas. */
  _createZoomToolbar(canvas, chartType) {
    const zoomable = ['line_chart', 'bar_chart', 'comparison_bar', 'scatter_chart'];
    if (!zoomable.includes(chartType)) return null;

    const wrapper = canvas.closest('.widget-chart-wrap') || canvas.parentElement;
    if (!wrapper) return null;

    // Remove existing toolbar
    const existing = wrapper.querySelector('.chart-zoom-toolbar');
    if (existing) existing.remove();

    const toolbar = document.createElement('div');
    toolbar.className = 'chart-zoom-toolbar';
    toolbar.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:4px 8px 2px;font-size:10px;color:#475569;';

    const hint = document.createElement('span');
    hint.textContent = 'Arrastrar: mover · Ctrl+rueda: zoom · Ctrl+arrastrar: seleccionar · Doble-clic: reset';
    hint.style.opacity = '0.7';

    const btn = document.createElement('button');
    btn.textContent = '\u21BA Reset Zoom';
    btn.style.cssText = 'display:none;padding:2px 10px;border-radius:4px;background:#1E293B;color:#e2e8f0;cursor:pointer;font-size:10px;border:1px solid #334155;transition:background .15s;';
    btn.onmouseenter = () => { btn.style.background = '#334155'; };
    btn.onmouseleave = () => { btn.style.background = '#1E293B'; };

    toolbar.appendChild(hint);
    toolbar.appendChild(btn);
    wrapper.insertBefore(toolbar, canvas);

    return btn;
  },

  /** Destroy all chart instances. */
  destroyAll(chartInstances) {
    Object.keys(chartInstances).forEach(key => {
      if (chartInstances[key]) chartInstances[key].destroy();
    });
    Object.keys(chartInstances).forEach(k => delete chartInstances[k]);
  },
};
