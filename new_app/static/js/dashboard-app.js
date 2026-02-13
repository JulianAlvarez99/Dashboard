/**
 * Dashboard App — Alpine.js component
 *
 * Manages:
 *  - Filter state and validation
 *  - Date/time validation with auto-correction
 *  - Line group detection and cascade
 *  - Applying filters via API validation endpoint
 *
 * Depends on: window.__dashboardConfig (bootstrapped from Jinja in index.html)
 *
 * Usage in template:
 *   <script>
 *     window.__dashboardConfig = {
 *       apiBase: '...',
 *       filters: [...],
 *       lineOptions: [...]
 *     };
 *   </script>
 *   <script src="/static/js/dashboard-app.js"></script>
 *   <div x-data="dashboardApp()" x-init="init()">
 */

function dashboardApp() {
  const config = window.__dashboardConfig || {};
  const filters = config.filters || [];
  const lineOptions = config.lineOptions || [];

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
    if (f.filter_type === 'daterange') return; // already handled
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

    // Filter params (initialized from filter configs)
    params: JSON.parse(JSON.stringify(initialParams)),

    // Multi-line group state
    isMultiLine: false,
    selectedLineGroup: null,

    // ── Lifecycle ────────────────────────────────────────────
    init() {
      console.log('[Dashboard] Initialized with', filters.length, 'filters');
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
        // Cascade: reload area options for single line
        try {
          var resp = await fetch(this.apiBase + '/api/v1/filters/areas?line_id=' + rawValue);
          if (resp.ok) {
            var opts = await resp.json();
            console.log('[Cascade] Areas for line', rawValue, ':', opts.length, 'options');
            // Areas will be re-rendered in Etapa 7 with HTMX partials
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
    },

    // ── Apply filters ───────────────────────────────────────
    async applyFilters() {
      this.loading = true;
      this.sidebarOpen = false;
      try {
        // Validate via API
        var resp = await fetch(this.apiBase + '/api/v1/filters/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.params),
        });
        var result = await resp.json();
        if (!result.valid) {
          console.warn('[Filters] Validation errors:', result.errors);
          return;
        }
        // Count active filters
        var count = 0;
        for (var k in this.params) {
          var v = this.params[k];
          if (v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)) count++;
        }
        this.filterCount = count;
        this.lastUpdate = new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
        // TODO: Etapa 6 — call orchestrator endpoint with cleaned params
        console.log('[Filters] Applied:', result.cleaned);
      } catch (e) {
        console.error('[Filters] Error:', e);
      } finally {
        this.loading = false;
      }
    },
  };
}
