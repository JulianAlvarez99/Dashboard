/**
 * Dashboard App - Alpine.js component
 *
 * Manages:
 *  - Filter state and validation
 *  - Loading filter options from the API cache
 *  - Applying filters (single POST to /api/v1/dashboard/data)
 *  - Distributing widget data and triggering chart renders
 *
 * Depends on: ChartRenderer (chart-renderer.js)
 *
 * Usage in template:
 *   <div x-data="dashboardApp(filterConfigs, widgetConfigs, apiBaseUrl)">
 */

function dashboardApp(filterConfigs, widgetConfigs, apiBaseUrl) {
    return {
        // ── Configuration ────────────────────────────────────────
        filterConfigs: filterConfigs || [],
        widgetConfigs: widgetConfigs || [],
        apiBaseUrl: apiBaseUrl || '',

        // ── State ────────────────────────────────────────────────
        loading: false,
        filterValues: {
            start_date: '',
            end_date: '',
            start_time: '00:00',
            end_time: '23:59'
        },
        options: {
            production_line: [],
            shift: [],
            product: [],
            area: []
        },
        widgetResults: {},
        chartInstances: {},
        queryMetadata: {
            total_detections: null,
            elapsed_ms: null
        },
        isMultiLine: false,
        selectedLineGroup: null,

        // ── Lifecycle ────────────────────────────────────────────

        async init() {
            this.initFilterValues();
            await this.loadOptions();
            await this.applyFilters();
        },

        // ═════════════════════════════════════════════════════════
        // Filter Values & Validation
        // ═════════════════════════════════════════════════════════

        initFilterValues() {
            this.filterConfigs.forEach(filter => {
                if (!filter) return;
                const paramName = filter.param_name;
                const defaultVal = filter.default_value;

                if (filter.filter_type === 'daterange') {
                    const daysBack = (defaultVal && defaultVal.days_back) || 7;
                    this.filterValues.start_date = this._daysAgo(daysBack);
                    this.filterValues.end_date = this._today();
                    this.filterValues.start_time = '00:00';
                    this.filterValues.end_time = '23:59';
                } else if (filter.filter_type === 'multiselect') {
                    this.filterValues[paramName] = defaultVal || [];
                } else if (filter.filter_type === 'toggle') {
                    this.filterValues[paramName] = defaultVal !== undefined ? defaultVal : false;
                } else {
                    this.filterValues[paramName] = defaultVal || '';
                }
            });
        },

        validateEndDate() {
            if (this.filterValues.start_date && this.filterValues.end_date) {
                if (this.filterValues.start_date > this.filterValues.end_date) {
                    this.filterValues.end_date = this.filterValues.start_date;
                }
                this.validateEndTime();
            }
        },

        validateEndTime() {
            if (this.filterValues.start_date === this.filterValues.end_date
                && this.filterValues.start_time && this.filterValues.end_time) {
                if (this.filterValues.start_time > this.filterValues.end_time) {
                    this.filterValues.end_time = this.filterValues.start_time;
                }
            }
        },

        // ═════════════════════════════════════════════════════════
        // Load Filter Options from Cache
        // ═════════════════════════════════════════════════════════

        async loadOptions() {
            try {
                const [linesRes, shiftsRes, productsRes] = await Promise.all([
                    fetch(`${this.apiBaseUrl}/api/v1/filters/options/production-lines`),
                    fetch(`${this.apiBaseUrl}/api/v1/filters/options/shifts`),
                    fetch(`${this.apiBaseUrl}/api/v1/filters/options/products`)
                ]);
                this.options.production_line = await linesRes.json();
                this.options.shift = await shiftsRes.json();
                this.options.product = await productsRes.json();
            } catch (error) {
                console.error('Error loading filter options:', error);
            }
        },

        async onLineChange() {
            const val = this.filterValues.line_id;
            // Check if it's a group or "all" selection
            const opt = this.options.production_line.find(o => String(o.value) === String(val));
            if (opt && opt.is_group) {
                this.isMultiLine = true;
                this.selectedLineGroup = opt.line_ids;
                // Disable downtime threshold for multi-line
                this.filterValues.downtime_threshold = null;
                this.options.area = [];
            } else if (val) {
                this.isMultiLine = false;
                this.selectedLineGroup = null;
                // Set downtime_threshold from the line's DB value
                if (opt && opt.downtime_threshold != null) {
                    this.filterValues.downtime_threshold = opt.downtime_threshold;
                }
                const res = await fetch(
                    `${this.apiBaseUrl}/api/v1/filters/options/areas?line_id=${val}`
                );
                this.options.area = await res.json();
            } else {
                // No line selected — treat as all lines
                this.isMultiLine = true;
                this.selectedLineGroup = null;
                this.filterValues.downtime_threshold = null;
                this.options.area = [];
            }
        },

        // ═════════════════════════════════════════════════════════
        // Apply Filters — Single Query Pipeline
        // ═════════════════════════════════════════════════════════

        async applyFilters() {
            if (this.loading) return;
            this.loading = true;

            const startTime = performance.now();

            const widgetIds = this.widgetConfigs.filter(w => w).map(w => w.widget_id);
            if (widgetIds.length === 0) {
                this.loading = false;
                return;
            }

            const body = this._buildRequestBody(widgetIds);

            try {
                const response = await fetch(`${this.apiBaseUrl}/api/v1/dashboard/data`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });

                if (!response.ok) throw new Error(`API error: ${response.status}`);

                const result = await response.json();
                const elapsed = Math.round(performance.now() - startTime);

                this.queryMetadata = {
                    total_detections: result.metadata?.total_detections || 0,
                    elapsed_ms: elapsed
                };

                // Destroy old charts before swapping data
                ChartRenderer.destroyAll(this.chartInstances);
                this.widgetResults = result.widgets || {};

                // Render charts — x-show becomes visible synchronously when
                // Alpine processes the reactive update, then we render on the
                // next animation frame when layout dimensions are available.
                this._renderAllCharts();

            } catch (error) {
                console.error('Error fetching dashboard data:', error);
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
         * Uses requestAnimationFrame to wait for x-show to
         * make containers visible and get layout dimensions.
         */
        _renderAllCharts() {
            const chartTypes = ['line_chart', 'bar_chart', 'pie_chart', 'comparison_bar', 'scatter_chart'];
            const chartWidgets = Object.values(this.widgetResults).filter(
                wd => wd && wd.data && chartTypes.includes(wd.widget_type)
            );

            if (chartWidgets.length === 0) return;

            // rAF waits for the browser to paint, ensuring x-show
            // has toggled visibility and elements have layout dimensions.
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    chartWidgets.forEach(wd => {
                        ChartRenderer.render(wd, this.chartInstances);
                    });
                });
            });
        },

        destroyAllCharts() {
            ChartRenderer.destroyAll(this.chartInstances);
        },

        /**
         * Re-render line charts only when curve_type changes.
         * Patches curve_type into existing widget data so ChartRenderer
         * picks it up without a full API refetch.
         */
        onCurveTypeChange() {
            const newCurve = this.filterValues.curve_type || 'smooth';
            // Patch the stored data for all line_chart widgets
            Object.values(this.widgetResults).forEach(wd => {
                if (wd && wd.widget_type === 'line_chart' && wd.data) {
                    wd.data.curve_type = newCurve;
                }
            });
            // Re-render all charts (line charts will pick up new curve_type)
            ChartRenderer.destroyAll(this.chartInstances);
            this._renderAllCharts();
        },

        // ═════════════════════════════════════════════════════════
        // Private helpers
        // ═════════════════════════════════════════════════════════

        _buildRequestBody(widgetIds) {
            const body = {
                widget_ids: widgetIds,
                start_date: this.filterValues.start_date || null,
                end_date: this.filterValues.end_date || null,
                start_time: this.filterValues.start_time || null,
                end_time: this.filterValues.end_time || null,
                interval: this.filterValues.interval || 'hour',
                curve_type: this.filterValues.curve_type || 'smooth'
            };

            // Handle multi-line (group or "all")
            if (this.isMultiLine && this.selectedLineGroup) {
                body.line_ids = this.selectedLineGroup.join(',');
            } else if (this.filterValues.line_id) {
                const val = this.filterValues.line_id;
                const opt = this.options.production_line.find(o => String(o.value) === String(val));
                if (opt && opt.is_group) {
                    body.line_ids = opt.line_ids.join(',');
                } else {
                    body.line_id = parseInt(val);
                }
            }

            if (this.filterValues.product_ids && this.filterValues.product_ids.length > 0)
                body.product_ids = this.filterValues.product_ids.join(',');
            if (this.filterValues.area_ids && this.filterValues.area_ids.length > 0)
                body.area_ids = this.filterValues.area_ids.join(',');
            if (this.filterValues.shift_id)
                body.shift_id = parseInt(this.filterValues.shift_id);
            if (this.filterValues.downtime_threshold != null)
                body.downtime_threshold = parseInt(this.filterValues.downtime_threshold);
            if (this.filterValues.show_downtime)
                body.show_downtime = true;

            return body;
        },

        _today() {
            return new Date().toISOString().split('T')[0];
        },

        _daysAgo(n) {
            return new Date(Date.now() - n * 86400000).toISOString().split('T')[0];
        }
    };
}
