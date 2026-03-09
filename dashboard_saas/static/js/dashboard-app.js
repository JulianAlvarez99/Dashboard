/**
 * Dashboard Alpine.js component — Main application state.
 *
 * Phase 3: Manages filter states, applies filters via API,
 * and displays raw data results.
 *
 * How it works:
 * 1. Reads server config from <script type="application/json" id="dashboard-config">
 * 2. Initializes filter states from default values
 * 3. On "Apply filters": POST to /api/v1/dashboard/apply-filters
 * 4. Displays raw data in the preview table
 */

'use strict';

function dashboardApp() {
    return {
        // ── UI state ────────────────────────────────────────────
        sidebarOpen: false,
        loading: false,

        // ── Server data (from JSON bootstrap) ───────────────────
        apiBase: '',
        filters: [],        // Filter configs from server
        widgets: [],         // Widget configs from server

        // ── Filter states (param_name → current value) ──────────
        filterStates: {},

        // ── Query result ────────────────────────────────────────
        rawData: [],            // Raw DB rows from last query
        lastQueryInfo: null,    // { row_count, tables_queried, query, params }

        // ── Line selection metadata (set by filter handler) ─────
        selectedLineInfo: null,

        // ── Init ────────────────────────────────────────────────

        init() {
            // Read server-injected config
            const configEl = document.getElementById('dashboard-config');
            if (configEl) {
                try {
                    const config = JSON.parse(configEl.textContent);
                    this.apiBase = config.apiBase || '';
                    this.filters = config.filters || [];
                    this.widgets = config.widgets || [];
                } catch (e) {
                    console.error('[Dashboard] Failed to parse config:', e);
                }
            }

            // Initialize filter states from defaults
            this.filters.forEach(filter => {
                this.filterStates[filter.param_name] = filter.default_value ?? '';
            });

            console.log('[Dashboard] Initialized with', this.filters.length, 'filters,',
                this.widgets.length, 'widgets');

            // Re-render Lucide icons after Alpine processes the DOM
            this.$nextTick(() => {
                if (window.lucide) lucide.createIcons();
            });
        },

        // ── Filter change handler ───────────────────────────────

        onFilterChange(paramName, value) {
            // Update state
            this.filterStates[paramName] = value;

            // Call the filter-specific JS handler if registered
            const handler = window.FilterHandlers && window.FilterHandlers[paramName];
            if (handler && handler.onChange) {
                const filter = this.filters.find(f => f.param_name === paramName);
                handler.onChange(this, value, filter);
            }

            console.log('[Dashboard] Filter changed:', paramName, '=', value);
        },

        // ── Apply filters (main data pipeline) ─────────────────

        async applyFilters() {
            // Validate required filters
            const lineValue = this.filterStates['line_id'];
            if (!lineValue) {
                alert('Seleccioná una línea de producción');
                return;
            }

            this.loading = true;
            this.rawData = [];
            this.lastQueryInfo = null;

            try {
                // Build the filter payload (only non-empty values)
                const payload = {};
                for (const [key, value] of Object.entries(this.filterStates)) {
                    if (value !== '' && value !== null && value !== undefined) {
                        payload[key] = value;
                    }
                }

                console.log('[Dashboard] Applying filters:', payload);

                // POST to the FastAPI endpoint
                const response = await fetch(`${this.apiBase}/api/v1/dashboard/apply-filters`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filters: payload }),
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                const result = await response.json();

                // Store results
                this.rawData = result.data || [];
                this.lastQueryInfo = {
                    row_count: result.row_count,
                    tables_queried: result.tables_queried,
                    query: result.query,
                    params: result.params,
                };

                console.log('[Dashboard] Query result:',
                    result.row_count, 'rows from', result.tables_queried.join(', '));

            } catch (err) {
                console.error('[Dashboard] Apply filters failed:', err);
                alert('Error al consultar datos: ' + err.message);
            } finally {
                this.loading = false;
            }
        },
    };
}
