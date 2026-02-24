/**
 * Dashboard Orchestrator
 *
 * Handles the complex multi-step processes of the dashboard:
 * 1. Fetching data and updating Alpine.js state (applyFilters)
 * 2. Re-computing data client-side (recomputeFromRaw)
 * 3. Rendering all charts (renderAllCharts)
 */
const DashboardOrchestrator = {

    /**
     * Main pipeline to validate, fetch, and update data.
     * @param {Object} ctx The Alpine.js component context (`this`)
     */
    async applyFilters(ctx) {
        if (ctx.loading) return;
        ctx.loading = true;
        const startTime = performance.now();

        try {
            const normalizedParams = this._normalizeParams(ctx.params);
            const valResult = await DashboardAPI.validateFilters(ctx.apiBase, normalizedParams);

            if (!valResult.valid) {
                console.warn('[Filters] Validation errors:', valResult.errors);
                this._showFilterError(valResult.errors);
                ctx.loading = false;
                return;
            }

            ctx.sidebarOpen = false;

            const body = this._buildRequestBody(ctx);
            const url = ctx.dashboardApiUrl || (ctx.apiBase + '/api/v1/dashboard/data');
            const result = await DashboardAPI.fetchDashboardData(url, body);
            const elapsed = Math.round(performance.now() - startTime);

            ctx._rawData = result.raw_data || null;
            ctx._rawDowntime = result.raw_downtime || null;
            ctx._shiftWindows = result.metadata?.shift_windows || {};
            ctx._lineConfig = result.metadata?.line_config || {};

            ctx.queryMetadata = {
                total_detections: result.metadata?.total_detections || 0,
                elapsed_ms: elapsed,
            };
            ctx.isMultiLine = result.metadata?.is_multi_line || false;

            ChartRenderer.destroyAll(ctx.chartInstances);

            ctx.widgetResults = result.widgets || {};
            ctx.hasData = Object.keys(ctx.widgetResults).length > 0;
            ctx.filtersApplied = true;

            ctx.filterCount = this._countActiveFilters(ctx.params);
            ctx.lastUpdate = new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });

            this.renderAllCharts(ctx);

            ctx.$nextTick(function () {
                if (typeof lucide !== 'undefined') lucide.createIcons();
            });

            console.log('[Dashboard] Data loaded —', Object.keys(ctx.widgetResults).length, 'widgets in', elapsed, 'ms');

        } catch (e) {
            console.error('[Dashboard] Error:', e);
            ctx.queryMetadata = { total_detections: null, elapsed_ms: null };
        } finally {
            ctx.loading = false;
        }
    },

    /**
     * Re-compute all computable widgets from _rawData without a new query.
     */
    recomputeFromRaw(ctx) {
        if (!ctx._rawData || ctx._rawData.length === 0) return;

        let rows = ctx._rawData.slice();
        let dt = ctx._rawDowntime ? ctx._rawDowntime.slice() : [];

        const shiftId = ctx.params.shift_id ? String(ctx.params.shift_id) : null;
        if (shiftId && ctx._shiftWindows[shiftId]) {
            const win = ctx._shiftWindows[shiftId];
            rows = DashboardDataEngine.sliceByShiftWindow(rows, win);
            dt = DashboardDataEngine.sliceDowntimeByWindow(dt, win);
        }

        const pids = (ctx.params.product_ids || []).map(Number);
        if (pids.length > 0) {
            rows = rows.filter(r => pids.indexOf(Number(r.product_id)) !== -1);
        }

        const interval = ctx.params.interval || 'hour';
        const shiftInfo = shiftId ? ctx._shiftWindows[shiftId] : null;

        Object.keys(ctx.widgetResults).forEach(wid => {
            const wd = ctx.widgetResults[wid];
            if (!wd) return;
            const meta = ctx._widgetMeta[parseInt(wid)] || ctx._widgetMeta[wid];
            if (!meta) return;

            const newData = DashboardDataEngine.recomputeWidget(meta.widget_name, rows, dt, interval, shiftInfo, ctx._lineConfig);
            if (newData !== null) {
                ctx.widgetResults[wid] = Object.assign({}, wd, { data: newData });
            }
        });

        ChartRenderer.destroyAll(ctx.chartInstances);
        this.renderAllCharts(ctx);
    },

    /**
     * Renders all charts orchestrating the interaction between HTML and ChartRenderer
     */
    renderAllCharts(ctx) {
        const chartWidgets = [];
        Object.keys(ctx.widgetResults).forEach(function (wid) {
            const wd = ctx.widgetResults[wid];
            if (!wd || !wd.data) return;
            const meta = ctx._widgetMeta[parseInt(wid)] || ctx._widgetMeta[wid];
            if (!meta) return;
            const chartType = ctx._CHART_TYPE_MAP[meta.widget_name];
            if (chartType) {
                chartWidgets.push({ chartType: chartType, widgetData: wd });
            }
        });

        if (chartWidgets.length === 0) return;

        const isMulti = ctx.isMultiLine;
        const instances = ctx.chartInstances;

        // Double rAF ensures Alpine x-show toggles display block so charts have dimensions
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                chartWidgets.forEach(cw => {
                    ChartRenderer.render(cw.chartType, cw.widgetData, instances, isMulti);
                });
            });
        });
    },

    // ─── Private Helpers ───────────────────────────────────────────

    _normalizeParams(params) {
        const out = JSON.parse(JSON.stringify(params));
        for (let k in out) {
            if (k === 'daterange') continue;
            if (out[k] === '') out[k] = null;
        }
        return out;
    },

    _countActiveFilters(params) {
        let count = 0;
        for (let k in params) {
            let v = params[k];
            if (v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)) count++;
        }
        return count;
    },

    _showFilterError(errors) {
        if (!errors || Object.keys(errors).length === 0) return;
        const msgs = Object.values(errors);
        const el = document.getElementById('filter-error-toast');
        if (el) {
            el.textContent = msgs.join(' · ');
            el.classList.remove('hidden');
            setTimeout(() => { el.classList.add('hidden'); }, 4000);
        } else {
            console.warn('[Filters]', msgs.join(', '));
        }
    },

    _buildRequestBody(ctx) {
        const body = {
            tenant_id: ctx.tenantId,
            role: ctx.role,
            daterange: ctx.params.daterange || null,
            interval: ctx.params.interval || 'hour',
            curve_type: ctx.params.curve_type || 'smooth',
            include_raw: true
        };

        if (ctx.isMultiLine && ctx.selectedLineGroup) {
            body.line_ids = ctx.selectedLineGroup.join(',');
        } else if (ctx.params.line_id) {
            const val = ctx.params.line_id;
            const opt = ctx._lineOptions.find(o => String(o.value) === String(val));
            if (opt && opt.extra && opt.extra.is_group) {
                body.line_ids = opt.extra.line_ids.join(',');
            } else {
                body.line_id = parseInt(val);
            }
        }

        if (ctx.params.product_ids && ctx.params.product_ids.length > 0)
            body.product_ids = ctx.params.product_ids.map(Number);
        if (ctx.params.area_ids && ctx.params.area_ids.length > 0)
            body.area_ids = ctx.params.area_ids.map(Number);
        if (ctx.params.shift_id)
            body.shift_id = parseInt(ctx.params.shift_id);
        if (ctx.params.downtime_threshold != null)
            body.downtime_threshold = parseInt(ctx.params.downtime_threshold);
        if (ctx.params.show_downtime)
            body.show_downtime = true;

        return body;
    }
};
