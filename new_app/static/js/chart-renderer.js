/**
 * Chart Renderer — Chart.js rendering and lifecycle
 *
 * Exposes a clean interface to render, update, or destroy charts.
 * Delegates the Chart.js configuration building to `ChartConfigBuilder` (chart-config.js).
 */
const ChartRenderer = {

  // ─── Render / destroy ─────────────────────────────────────

  /**
   * Render (or re-render) a chart for the given widget data.
   *
   * @param {string}  chartType      - Chart type key (line_chart, bar_chart, etc.)
   * @param {Object}  widgetData     - The widget data from the API
   * @param {Object}  chartInstances - Map of canvasId → Chart instance
   * @param {boolean} isMultiLine    - Whether multi-line mode is active
   * @param {number}  _attempt       - Internal retry counter
   * @param {string}  mode           - For line_chart: 'line' (default) | 'bar'
   * @returns {Chart|null}
   */
  render(chartType, widgetData, chartInstances, isMultiLine, _attempt, mode) {
    if (!widgetData || !widgetData.data) return null;

    const canvasId = `chart-${widgetData.widget_id}`;
    const canvas = document.getElementById(canvasId);

    // Retry up to 10 times if canvas not yet in DOM
    if (!canvas || canvas.offsetWidth === 0) {
      const attempt = (_attempt || 0) + 1;
      if (attempt <= 10) {
        setTimeout(() => this.render(chartType, widgetData, chartInstances, isMultiLine, attempt, mode), 60);
      }
      return null;
    }

    // Destroy existing chart on this canvas
    // Alpine wraps stored objects in a reactive Proxy — use Alpine.raw() so
    // Chart.js destroy() receives the real class instance (not the proxy).
    if (chartInstances[canvasId]) {
      const rawChart = (typeof Alpine !== 'undefined' && Alpine.raw)
        ? Alpine.raw(chartInstances[canvasId])
        : chartInstances[canvasId];
      rawChart.destroy();
      delete chartInstances[canvasId];
    }

    const resetBtn = this._createZoomToolbar(canvas, chartType, mode);

    // Delegate to the config builder
    const config = ChartConfigBuilder.getConfig(chartType, widgetData.data, resetBtn, isMultiLine, mode);
    if (!config) return null;

    const chart = new Chart(canvas.getContext('2d'), config);
    chartInstances[canvasId] = chart;

    // Wire reset button
    if (resetBtn) {
      resetBtn.onclick = () => { chart.resetZoom(); resetBtn.style.display = 'none'; };
      canvas.addEventListener('dblclick', () => { chart.resetZoom(); resetBtn.style.display = 'none'; });
    }

    return chart;
  },

  /**
   * Toggle between 'line' and 'bar' view for a production timeline chart.
   * Re-renders the chart in-place, preserving all data, annotations and zoom.
   *
   * @param {string}  widgetId       - Widget ID (string or number)
   * @param {string}  mode           - 'line' | 'bar'
   * @param {Object}  widgetData     - The stored widget data from API (widgetResults[id])
   * @param {Object}  chartInstances - Map of canvasId → Chart instance
   * @param {boolean} isMultiLine    - Whether multi-line mode is active
   */
  toggleChartMode(widgetId, mode, widgetData, chartInstances, isMultiLine) {
    this.render('line_chart', widgetData, chartInstances, isMultiLine, 0, mode);
  },

  /** Create zoom toolbar above the canvas. */
  _createZoomToolbar(canvas, chartType, mode) {
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

    // Hint text differs for bar mode (no pan in bar mode)
    const hintText = (chartType === 'line_chart' && mode === 'bar')
        ? 'Ctrl+rueda: zoom · Doble-clic: reset'
        : 'Arrastrar: mover · Ctrl+rueda: zoom · Doble-clic: reset';

    const hint = document.createElement('span');
    hint.textContent = hintText;
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

  /**
   * Update curve type on all line charts in-place (no destroy/recreate).
   * @param {Object} chartInstances - Map of canvasId → Chart instance
   * @param {string} curveType      - New curve type key
   */
  updateCurveType(chartInstances, curveType) {
    const curve = ChartConfigBuilder.getCurveProps(curveType);
    const stacked = curveType === 'stacked';
    Object.keys(chartInstances).forEach(function (canvasId) {
      let chartProxy = chartInstances[canvasId];
      let chart = typeof Alpine !== 'undefined' && Alpine.raw ? Alpine.raw(chartProxy) : chartProxy;
      if (!chart || chart.config.type !== 'line') return;
      chart.data.datasets.forEach(function (ds) {
        ds.tension = curve.tension;
        ds.stepped = curve.stepped;
        ds.fill = stacked ? 'origin' : false;
      });
      if (chart.options.scales && chart.options.scales.x) chart.options.scales.x.stacked = stacked;
      if (chart.options.scales && chart.options.scales.y) chart.options.scales.y.stacked = stacked;
      chart.update();
    });
  },

  /**
   * Toggle downtime annotations on all line charts in-place.
   * @param {Object} chartInstances  - Map of canvasId → Chart instance
   * @param {Array}  downtimeEvents  - Original downtime_events array (or empty)
   * @param {boolean} show           - Whether to show or hide annotations
   */
  updateDowntimeAnnotations(chartInstances, downtimeEvents, show) {
    Object.keys(chartInstances).forEach(function (canvasId) {
      let chartProxy = chartInstances[canvasId];
      let chart = typeof Alpine !== 'undefined' && Alpine.raw ? Alpine.raw(chartProxy) : chartProxy;
      if (!chart || chart.config.type !== 'line') return;
      if (!chart.options.plugins) chart.options.plugins = {};
      if (show && downtimeEvents && downtimeEvents.length > 0) {
        chart.options.plugins.annotation = { annotations: ChartConfigBuilder.buildDowntimeAnnotations(downtimeEvents) };
      } else {
        chart.options.plugins.annotation = false;
      }
      chart.update();
    });
  },

  /** Destroy all chart instances. */
  destroyAll(chartInstances) {
    Object.keys(chartInstances).forEach(key => {
      if (chartInstances[key]) {
        const raw = (typeof Alpine !== 'undefined' && Alpine.raw)
          ? Alpine.raw(chartInstances[key])
          : chartInstances[key];
        raw.destroy();
      }
    });
    Object.keys(chartInstances).forEach(k => delete chartInstances[k]);
  },
};
