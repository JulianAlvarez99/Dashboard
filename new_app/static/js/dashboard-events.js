/**
 * Dashboard Events
 *
 * Provides all the Alpine.js UI event handlers.
 * These are mixed into the main `dashboardApp` state object.
 */
const DashboardEvents = {

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
        const arr = this.params[param];
        const idx = arr.indexOf(value);
        if (idx === -1) arr.push(value);
        else arr.splice(idx, 1);

        // Trigger client-side re-aggregation for product filter (Etapa 3)
        if (param === 'product_ids') {
            this.onProductIdsChange();
        }
    },

    // ── Line change cascade ─────────────────────────────────
    async onLineChange(rawValue) {
        const opt = this._lineOptions.find(o => String(o.value) === String(rawValue));

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
                const areas = await DashboardAPI.fetchAreas(this.apiBase, rawValue);
                console.log('[Cascade] Areas for line', rawValue, ':', areas.length, 'options');
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
        this.params = JSON.parse(JSON.stringify(this._initialParams));
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

    /**
     * Re-render line charts when curve_type changes.
     * Patches the new curve_type into the data so the config builder picks it
     * up on the next full render, then updates all charts.
     */
    onCurveTypeChange() {
        if (!this.hasData) return;

        // Wait for Alpine model to sync, then push update to Chart.js
        this.$nextTick(() => {
            const newCurve = this.params.curve_type || 'smooth';

            // Patch curve_type into every chart widget's data
            Object.keys(this.widgetResults).forEach(wid => {
                const wd = this.widgetResults[wid];
                if (wd && wd.data) {
                    wd.data.curve_type = newCurve;
                }
            });

            ChartRenderer.updateCurveType(this.chartInstances, newCurve);
        });
    },

    /**
     * Show downtime toggle — patch flag into line-chart widgets and re-render.
     * Avoids full re-query.
     */
    onShowDowntimeChange() {
        if (!this.hasData) return;
        const show = !!this.params.show_downtime;

        // Patch show_downtime into every chart widget's data
        Object.keys(this.widgetResults).forEach(wid => {
            const wd = this.widgetResults[wid];
            if (wd && wd.data) {
                wd.data.show_downtime = show;
            }
        });

        ChartRenderer.updateDowntimeAnnotations(this.chartInstances, this._rawDowntime || [], show);
    },

    /**
     * Search filter — client-side filtering of table/ranking rows.
     * Forces Alpine reactivity by replacing the widgetResults[wid] reference.
     */
    onSearchChange() {
        if (!this.hasData) return;
        const query = (this.params.search || '').toLowerCase().trim();

        Object.keys(this.widgetResults).forEach(wid => {
            const wd = this.widgetResults[wid];
            if (!wd || !wd.data || !wd.data.rows) return;

            if (!wd._original_rows) {
                wd._original_rows = wd.data.rows.slice();
            }

            const filtered = !query
                ? wd._original_rows.slice()
                : wd._original_rows.filter(row => {
                    return Object.values(row).some(val => typeof val === 'string' && val.toLowerCase().includes(query));
                });

            // Force Alpine reactivity
            this.widgetResults[wid] = Object.assign({}, wd, {
                data: Object.assign({}, wd.data, { rows: filtered }),
            });
        });
    },

    /**
     * Interval change — re-aggregate raw data client-side (no re-query).
     */
    onIntervalChange() {
        if (!this.hasData) return;
        if (this._rawData && this._rawData.length > 0) {
            DashboardOrchestrator.recomputeFromRaw(this);
        } else {
            this._debouncedApply();
        }
    },

    /**
     * Shift change — slice raw data by shift's time window (no re-query).
     */
    onShiftChange() {
        if (!this.hasData) return;
        if (this._rawData && this._rawData.length > 0) {
            DashboardOrchestrator.recomputeFromRaw(this);
        } else {
            this._debouncedApply();
        }
    },

    /**
     * Product IDs change — filter raw data client-side (no re-query).
     */
    onProductIdsChange() {
        if (!this.hasData) return;
        if (this._rawData && this._rawData.length > 0) {
            DashboardOrchestrator.recomputeFromRaw(this);
        } else {
            this._debouncedApply();
        }
    },

    /** Debounced apply — prevents multiple rapid fire calls. */
    _debouncedApply() {
        if (this._applyTimer) clearTimeout(this._applyTimer);
        this._applyTimer = setTimeout(() => {
            this._applyTimer = null;
            if (!this.loading) this.applyFilters();
        }, 250);
    }
};
