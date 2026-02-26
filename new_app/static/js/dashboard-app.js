/**
 * Dashboard App — Alpine.js component
 *
 * This file acts purely as the state container and initialization point.
 * All complex logic has been modularized:
 *  - Filtering and formatting rules -> DashboardEvents (dashboard-events.js)
 *  - Orchestration & Querying -> DashboardOrchestrator (dashboard-orchestrator.js)
 *  - Client-side data math -> DashboardDataEngine (data-engine.js)
 *  - API calls -> DashboardAPI (api-client.js)
 */
function dashboardApp() {
  // Parse configuration injected via <script type="application/json">
  let config = {};
  try {
    const configEl = document.getElementById('dashboard-config');
    if (configEl) {
      config = JSON.parse(configEl.textContent);
    }
  } catch (e) {
    console.error("[Dashboard] Failed to parse dashboard config JSON", e);
  }

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
    'ProductionTimeChart': 'line_chart',
    'AreaDetectionChart': 'bar_chart',
    'ProductDistributionChart': 'pie_chart',
    'EntryOutputCompareChart': 'comparison_bar',
    'ScatterChart': 'scatter_chart',
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

  // ── Alpine State ───────────────────────────────────────────
  const state = {
    sidebarOpen: false,
    loading: false,
    hasData: false,
    filtersApplied: false,
    activeTab: 'produccion',    // Tab switcher: 'produccion' | 'oee'
    lastUpdate: null,
    filterCount: 0,
    apiBase: config.apiBase || '',
    dashboardApiUrl: config.dashboardApiUrl || '',
    tenantId: config.tenantId || null,
    role: config.role || 'ADMIN',

    // Filter params
    params: JSON.parse(JSON.stringify(initialParams)),
    _initialParams: initialParams,

    // Multi-line group state
    isMultiLine: false,
    selectedLineGroup: null,

    // Widget data from API
    widgetResults: {},
    chartInstances: {},
    // Chart display mode per widget — 'line' | 'bar' (only applies to line_chart type)
    // Change via toggle buttons in the widget header.
    chartModes: {},
    queryMetadata: {
      total_detections: null,
      elapsed_ms: null,
    },

    // ── Globals tracked for Orchestrator bounds ──
    _lineOptions: lineOptions,
    _widgetMeta: widgetMeta,
    _CHART_TYPE_MAP: CHART_TYPE_MAP,

    // ── Raw data buffers (Etapa 3 — client-side re-aggregation) ──
    _rawData: null,
    _rawDowntime: null,
    _shiftWindows: {},
    _lineConfig: {},

    // ── Lifecycle ────────────────────────────────────────────
    init() {
      console.log('[Dashboard] Initialized —', filters.length, 'filters,', widgets.length, 'widgets');
      this.$nextTick(function () {
        if (typeof lucide !== 'undefined') lucide.createIcons();
      });
    },

    // ── Orchestrator Delegation ──────────────────────────────
    async applyFilters() {
      await DashboardOrchestrator.applyFilters(this);
    }
  };

  // Mix in all the UI events
  return Object.assign(state, DashboardEvents);
}
