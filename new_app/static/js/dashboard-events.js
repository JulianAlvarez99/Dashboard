/**
 * Dashboard Events
 *
 * Provides the Alpine.js UI event handlers that are NOT owned by a specific
 * filter class.  Filter-specific handlers (onLineChange, onShiftChange,
 * onIntervalChange, onCurveTypeChange, onShowDowntimeChange, onSearchChange,
 * onProductIdsChange, validateEndDate, validateEndTime) live in each filter's
 * `js_inline` attribute and are injected into the Alpine component at runtime
 * by the template's IIFE — they take precedence over anything defined here via
 * Object.assign, so they must NOT be duplicated here.
 */
const DashboardEvents = {

    // ── Multiselect toggle ──────────────────────────────────
    toggleMultiselect(param, value) {
        const fs = this.filterStates[param];
        if (!fs) return;
        const arr = fs.value;
        const idx = arr.indexOf(value);
        if (idx === -1) arr.push(value);
        else arr.splice(idx, 1);

        // Trigger client-side re-aggregation for product filter (Etapa 3)
        if (param === 'product_ids') {
            this.onProductIdsChange();
        }
    },

    // ── Reset filters ───────────────────────────────────────
    resetFilters() {
        for (const [key, initial] of Object.entries(this._initialFilterStates)) {
            if (this.filterStates[key]) {
                // Deep copy to avoid mutating the initial object
                this.filterStates[key].value = JSON.parse(JSON.stringify(initial.value));
            }
        }
        this.isMultiLine = false;
        this.selectedLineGroup = null;
        this.hasData = false;
        this.filtersApplied = false;
        this.filterCount = 0;
        this.queryMetadata = { total_detections: null, elapsed_ms: null };
        ChartRenderer.destroyAll(this.chartInstances);
        this.widgetResults = {};
    },

    /**
     * Toggle a production timeline widget between line and bar chart mode.
     * Re-renders the chart immediately without re-fetching data.
     *
     * @param {string|number} wid  - Widget ID (matches widgetResults key)
     * @param {string}        mode - 'line' | 'bar'
     */
    toggleWidgetMode(wid, mode) {
        this.chartModes[wid] = mode;
        const wd = this.widgetResults[wid];
        if (!wd) return;
        const isMulti = this.isMultiLine;
        const instances = this.chartInstances;
        // Double rAF ensures the canvas is visible if tab just became active
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                ChartRenderer.toggleChartMode(wid, mode, wd, instances, isMulti);
            });
        });
    },

    /** Debounced apply — prevents multiple rapid-fire calls from filter events. */
    _debouncedApply() {
        if (this._applyTimer) clearTimeout(this._applyTimer);
        this._applyTimer = setTimeout(() => {
            this._applyTimer = null;
            if (!this.loading) this.applyFilters();
        }, 250);
    },
};
