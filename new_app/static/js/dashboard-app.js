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
  // Derive line options from the filter config (options are embedded server-side).
  // Falls back to config.lineOptions for backward compatibility.
  const _lineFilterCfg = filters.find(function(f) { return f.param_name === 'line_id'; });
  const lineOptions = (_lineFilterCfg && Array.isArray(_lineFilterCfg.options) && _lineFilterCfg.options.length > 0)
    ? _lineFilterCfg.options
    : (config.lineOptions || []);

  // ── Build widget metadata map {widget_id → widget info} ────
  const widgetMeta = {};
  widgets.forEach(function (w) {
    if (w && w.widget_id) widgetMeta[w.widget_id] = w;
  });

  // ── Build filterStates from filter configs ────────────────
  const filterStates = {};
  filters.forEach(function (f) {
    let initialValue;
    switch (f.filter_type) {
      case 'daterange':
        initialValue = f.default_value || {
          start_date: new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10),
          end_date:   new Date().toISOString().slice(0, 10),
          start_time: '00:00',
          end_time:   '23:59',
        };
        break;
      case 'multiselect':
        initialValue = Array.isArray(f.default_value) ? f.default_value : [];
        break;
      case 'toggle':
        initialValue = f.default_value !== undefined ? f.default_value : false;
        break;
      case 'number':
        initialValue = f.default_value !== undefined ? f.default_value : null;
        break;
      default:
        initialValue = (f.default_value !== null && f.default_value !== undefined)
          ? f.default_value : null;
    }
    filterStates[f.param_name] = {
      value:      initialValue,
      type:       f.filter_type,
      serialize:  (f.js_behavior && f.js_behavior.serialize)  || 'raw',
      include_if: (f.js_behavior && f.js_behavior.include_if) || 'truthy',
      on_change:  (f.js_behavior && f.js_behavior.on_change)  || '',
      options:    f.options || [],
      validation: f.js_validation || null,
    };
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

    // ── filterStates: single source of truth for all filter values ──
    filterStates: JSON.parse(JSON.stringify(filterStates)),
    _initialFilterStates: filterStates,

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
    // chart_type is now read from meta.chart_type (widget_layout backend data)
    // — the local CHART_TYPE_MAP constant has been removed (T-13)

    // ── Raw data buffers (Etapa 3 — client-side re-aggregation) ──
    _rawData: null,
    _rawDowntime: null,
    // ── Lazy loading: tabs ya renderizadas ──
    _renderedTabs: null,  // se inicializa como Set en el primer uso
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
