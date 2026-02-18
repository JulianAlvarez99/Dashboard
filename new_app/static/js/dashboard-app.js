/**
 * Dashboard App — Alpine.js component
 *
 * Manages:
 *  - Filter state and validation
 *  - Date/time validation with auto-correction
 *  - Line group detection and cascade
 *  - Applying filters via POST /api/v1/dashboard/data
 *  - Distributing widget data and triggering chart renders
 *
 * Depends on:
 *   - window.__dashboardConfig (bootstrapped from Jinja in index.html)
 *   - ChartRenderer (chart-renderer.js)
 *
 * Usage in template:
 *   <div x-data="dashboardApp()" x-init="init()">
 */

function dashboardApp() {
  const config = window.__dashboardConfig || {};
  const filters = config.filters || [];
  const widgets = config.widgets || [];
  const lineOptions = config.lineOptions || [];

  // ── Build widget metadata map {widget_id → widget info} ────
  const widgetMeta = {};
  widgets.forEach(function (w) {
    if (w && w.widget_id) widgetMeta[w.widget_id] = w;
  });

  // ── Chart type map from widget class → chart_type ──────────
  const CHART_TYPE_MAP = {
    'ProductionTimeChart':      'line_chart',
    'AreaDetectionChart':       'bar_chart',
    'ProductDistributionChart': 'pie_chart',
    'EntryOutputCompareChart':  'comparison_bar',
    'ScatterChart':             'scatter_chart',
  };

  // ── Build initial params from filter configs ──────────────
  const initialParams = {
    daterange: {
      start_date: new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10),
      end_date: new Date().toISOString().slice(0, 10),
      start_time: '00:00',
      end_time: '23:59',
    },
  };

  filters.forEach(function (f) {
    if (f.filter_type === 'daterange') return;
    if (f.filter_type === 'multiselect') {
      initialParams[f.param_name] = f.default_value || [];
    } else if (f.filter_type === 'toggle') {
      initialParams[f.param_name] = f.default_value !== undefined ? f.default_value : false;
    } else if (f.filter_type === 'number') {
      initialParams[f.param_name] = f.default_value !== undefined ? f.default_value : null;
    } else {
      initialParams[f.param_name] = f.default_value !== undefined && f.default_value !== null
        ? f.default_value
        : null;
    }
  });

  return {
    // ── State ────────────────────────────────────────────────
    sidebarOpen: false,
    loading: false,
    hasData: false,
    lastUpdate: null,
    filterCount: 0,
    apiBase: config.apiBase || '',
    dashboardApiUrl: config.dashboardApiUrl || '',
    tenantId: config.tenantId || null,
    role: config.role || 'ADMIN',

    // Filter params
    params: JSON.parse(JSON.stringify(initialParams)),

    // Multi-line group state
    isMultiLine: false,
    selectedLineGroup: null,

    // Widget data from API
    widgetResults: {},
    chartInstances: {},
    queryMetadata: {
      total_detections: null,
      elapsed_ms: null,
    },

    // ── Lifecycle ────────────────────────────────────────────
    init() {
      console.log('[Dashboard] Initialized —', filters.length, 'filters,', widgets.length, 'widgets');
      this.$nextTick(function () { lucide.createIcons(); });
    },

    // ── Date/Time validation ────────────────────────────────
    validateEndDate() {
      if (this.params.daterange.start_date && this.params.daterange.end_date) {
        if (this.params.daterange.start_date > this.params.daterange.end_date) {
          this.params.daterange.end_date = this.params.daterange.start_date;
        }
        this.validateEndTime();
      }
    },

    validateEndTime() {
      if (this.params.daterange.start_date === this.params.daterange.end_date
          && this.params.daterange.start_time && this.params.daterange.end_time) {
        if (this.params.daterange.start_time > this.params.daterange.end_time) {
          this.params.daterange.end_time = this.params.daterange.start_time;
        }
      }
    },

    // ── Multiselect toggle ──────────────────────────────────
    toggleMultiselect(param, value) {
      var arr = this.params[param];
      var idx = arr.indexOf(value);
      if (idx === -1) arr.push(value);
      else arr.splice(idx, 1);
    },

    // ── Line change cascade ─────────────────────────────────
    async onLineChange(rawValue) {
      var opt = lineOptions.find(function (o) {
        return String(o.value) === String(rawValue);
      });

      if (opt && opt.extra && opt.extra.is_group) {
        this.isMultiLine = true;
        this.selectedLineGroup = opt.extra.line_ids;
        this.params.area_ids = [];
        console.log('[Line] Group selected:', opt.label, '→ lines', opt.extra.line_ids);
      } else if (rawValue) {
        this.isMultiLine = false;
        this.selectedLineGroup = null;
        // Cascade: reload area options
        try {
          var resp = await fetch(this.apiBase + '/api/v1/filters/areas?line_id=' + rawValue);
          if (resp.ok) {
            var opts = await resp.json();
            console.log('[Cascade] Areas for line', rawValue, ':', opts.length, 'options');
          }
        } catch (e) {
          console.warn('[Cascade] Failed:', e);
        }
      } else {
        this.isMultiLine = false;
        this.selectedLineGroup = null;
      }
    },

    // ── Reset filters ───────────────────────────────────────
    resetFilters() {
      this.params = JSON.parse(JSON.stringify(initialParams));
      this.hasData = false;
      this.filterCount = 0;
      this.queryMetadata = { total_detections: null, elapsed_ms: null };
      ChartRenderer.destroyAll(this.chartInstances);
      this.widgetResults = {};
    },

    // ═════════════════════════════════════════════════════════
    // Apply Filters — Single Query Pipeline
    // ═════════════════════════════════════════════════════════

    async applyFilters() {
      if (this.loading) return;
      this.loading = true;
      this.sidebarOpen = false;

      var startTime = performance.now();

      try {
        // 1. Validate via API
        var valResp = await fetch(this.apiBase + '/api/v1/filters/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.params),
        });
        var valResult = await valResp.json();
        if (!valResult.valid) {
          console.warn('[Filters] Validation errors:', valResult.errors);
          this.loading = false;
          return;
        }

        // 2. Build request body for orchestrator
        var body = this._buildRequestBody();

        // 3. Call orchestrator endpoint
        var url = this.dashboardApiUrl || (this.apiBase + '/api/v1/dashboard/data');
        var response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        if (!response.ok) throw new Error('API error: ' + response.status);

        var result = await response.json();
        var elapsed = Math.round(performance.now() - startTime);

        // 4. Store metadata
        this.queryMetadata = {
          total_detections: result.metadata?.total_detections || 0,
          elapsed_ms: elapsed,
        };
        this.isMultiLine = result.metadata?.is_multi_line || false;

        // 5. Destroy old charts before swapping data
        ChartRenderer.destroyAll(this.chartInstances);

        // 6. Set widget results (Alpine reactivity triggers DOM updates)
        this.widgetResults = result.widgets || {};
        this.hasData = Object.keys(this.widgetResults).length > 0;

        // 7. Count active filters
        var count = 0;
        for (var k in this.params) {
          var v = this.params[k];
          if (v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)) count++;
        }
        this.filterCount = count;
        this.lastUpdate = new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });

        // 8. Render charts after Alpine processes reactivity
        this._renderAllCharts();

        // 9. Re-initialize Lucide icons for new DOM elements
        this.$nextTick(function () { lucide.createIcons(); });

        console.log('[Dashboard] Data loaded —', Object.keys(this.widgetResults).length, 'widgets in', elapsed, 'ms');

      } catch (e) {
        console.error('[Dashboard] Error:', e);
        this.queryMetadata = { total_detections: null, elapsed_ms: null };
      } finally {
        this.loading = false;
      }
    },

    // ═════════════════════════════════════════════════════════
    // Chart rendering (delegates to ChartRenderer)
    // ═════════════════════════════════════════════════════════

    /**
     * Render all chart-type widgets.
     * Uses double-rAF to wait for Alpine x-show to finish toggling
     * visibility, ensuring canvases have layout dimensions.
     */
    _renderAllCharts() {
      var self = this;
      var chartWidgets = [];

      // Find chart widgets by matching widget_id ← widgetMeta ← CHART_TYPE_MAP
      Object.keys(this.widgetResults).forEach(function (wid) {
        var wd = self.widgetResults[wid];
        if (!wd || !wd.data) return;
        var meta = widgetMeta[parseInt(wid)] || widgetMeta[wid];
        if (!meta) return;
        var chartType = CHART_TYPE_MAP[meta.widget_name];
        if (chartType) {
          chartWidgets.push({ chartType: chartType, widgetData: wd });
        }
      });

      if (chartWidgets.length === 0) return;

      var isMulti = this.isMultiLine;
      var instances = this.chartInstances;

      // Double rAF ensures x-show has toggled and layout is computed
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          chartWidgets.forEach(function (cw) {
            ChartRenderer.render(cw.chartType, cw.widgetData, instances, isMulti);
          });
        });
      });
    },

    /**
     * Re-render line charts when curve_type changes.
     */
    onCurveTypeChange() {
      var newCurve = this.params.curve_type || 'smooth';
      var self = this;
      Object.values(this.widgetResults).forEach(function (wd) {
        if (wd && wd.widget_type === 'chart' && wd.data) {
          wd.data.curve_type = newCurve;
        }
      });
      ChartRenderer.destroyAll(this.chartInstances);
      this._renderAllCharts();
    },

    // ═════════════════════════════════════════════════════════
    // Private helpers
    // ═════════════════════════════════════════════════════════

    _buildRequestBody() {
      var body = {
        tenant_id: this.tenantId,
        role: this.role,
        daterange: this.params.daterange || null,
        interval: this.params.interval || 'hour',
        curve_type: this.params.curve_type || 'smooth',
      };

      // Handle multi-line (group or "all")
      if (this.isMultiLine && this.selectedLineGroup) {
        body.line_ids = this.selectedLineGroup.join(',');
      } else if (this.params.line_id) {
        var val = this.params.line_id;
        var opt = lineOptions.find(function (o) { return String(o.value) === String(val); });
        if (opt && opt.extra && opt.extra.is_group) {
          body.line_ids = opt.extra.line_ids.join(',');
        } else {
          body.line_id = parseInt(val);
        }
      }

      if (this.params.product_ids && this.params.product_ids.length > 0)
        body.product_ids = this.params.product_ids.map(Number);
      if (this.params.area_ids && this.params.area_ids.length > 0)
        body.area_ids = this.params.area_ids.map(Number);
      if (this.params.shift_id)
        body.shift_id = parseInt(this.params.shift_id);
      if (this.params.downtime_threshold != null)
        body.downtime_threshold = parseInt(this.params.downtime_threshold);
      if (this.params.show_downtime)
        body.show_downtime = true;

      return body;
    },
  };
}
