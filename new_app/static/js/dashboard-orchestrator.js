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
            const valResult = this._validateParamsLocally(normalizedParams);

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
            // Resetear tabs renderizadas para lazy loading
            ctx._renderedTabs = new Set();

            ctx.widgetResults = result.widgets || {};
            ctx.hasData = Object.keys(ctx.widgetResults).length > 0;
            ctx.filtersApplied = true;

            ctx.filterCount = this._countActiveFilters(ctx.params);
            ctx.lastUpdate = new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });

            this._renderTabCharts(ctx, ctx.activeTab);

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
        ctx._renderedTabs = new Set();
        this._renderTabCharts(ctx, ctx.activeTab);
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
            const chartType = meta.chart_type;
            if (chartType) {
                chartWidgets.push({ chartType: chartType, widgetData: wd, wid });
            }
        });

        if (chartWidgets.length === 0) return;

        const isMulti = ctx.isMultiLine;
        const instances = ctx.chartInstances;
        const modes = ctx.chartModes || {};

        // Double rAF ensures Alpine x-show toggles display block so charts have dimensions
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                chartWidgets.forEach(cw => {
                    const mode = modes[cw.wid] || 'line';
                    ChartRenderer.render(cw.chartType, cw.widgetData, instances, isMulti, 0, mode);
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

    /**
     * Validación local de parámetros — reemplaza el round-trip HTTP a
     * /api/v1/filters/validate. Solo verifica las reglas que el browser
     * puede evaluar sin consultar el servidor.
     *
     * Retorna el mismo shape que DashboardAPI.validateFilters():
     *   { valid: boolean, errors: { param_name: "mensaje" } }
     *
     * La validación profunda (tipos, rangos, existencia en DB) sigue
     * ocurriendo en el backend dentro de DashboardOrchestrator.execute().
     *
     * @param {Object} params - Parámetros normalizados
     * @returns {{ valid: boolean, errors: Object }}
     */
    _validateParamsLocally(params) {
        const errors = {};

        // Regla 1: daterange obligatorio con start_date y end_date
        const dr = params.daterange;
        if (!dr || typeof dr !== 'object') {
            errors['daterange'] = 'El rango de fechas es obligatorio';
        } else {
            if (!dr.start_date || !/^\d{4}-\d{2}-\d{2}$/.test(dr.start_date)) {
                errors['daterange'] = 'Fecha de inicio inválida (formato YYYY-MM-DD)';
            } else if (!dr.end_date || !/^\d{4}-\d{2}-\d{2}$/.test(dr.end_date)) {
                errors['daterange'] = 'Fecha de fin inválida (formato YYYY-MM-DD)';
            } else if (dr.start_date > dr.end_date) {
                errors['daterange'] = 'La fecha de inicio debe ser anterior a la fecha de fin';
            }
        }

        // Regla 2: line_id obligatorio (null o vacío no permitido)
        const lid = params.line_id;
        if (lid === null || lid === undefined || lid === '') {
            errors['line_id'] = 'Seleccioná una línea de producción';
        }

        // Regla 3: interval debe ser uno de los valores conocidos
        const validIntervals = ['minute', '15min', 'hour', 'day', 'week', 'month'];
        if (params.interval && !validIntervals.includes(params.interval)) {
            errors['interval'] = `Intervalo inválido: ${params.interval}`;
        }

        // Regla 4: downtime_threshold si está presente debe ser número positivo
        const dt = params.downtime_threshold;
        if (dt !== null && dt !== undefined) {
            const parsed = Number(dt);
            if (isNaN(parsed) || parsed < 0) {
                errors['downtime_threshold'] = 'El umbral de parada debe ser un número positivo';
            }
        }

        return {
            valid: Object.keys(errors).length === 0,
            errors,
        };
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
    },

    /**
     * Lazy load: renderizar solo los widgets de una tab específica.
     * Usa _widgetMeta para filtrar por tab (mismo campo que widget_layout.py).
     */
    _renderTabCharts(ctx, tab) {
        if (!ctx.hasData) return;

        // Inicializar Set si no existe
        if (!(ctx._renderedTabs instanceof Set)) {
            ctx._renderedTabs = new Set();
        }

        const widgetMeta = ctx._widgetMeta || {};
        const isMulti = ctx.isMultiLine;
        const instances = ctx.chartInstances;
        const modes = ctx.chartModes || {};

        // Construir lista de widgets de este tab
        const tabCharts = [];
        Object.keys(ctx.widgetResults).forEach(wid => {
            const wd = ctx.widgetResults[wid];
            if (!wd || !wd.data) return;
            const meta = widgetMeta[parseInt(wid)] || widgetMeta[wid];
            if (!meta) return;
            // Filtrar por tab: si el widget no tiene tab definido, pertenece a 'produccion'
            const widgetTab = meta.tab || 'produccion';
            if (widgetTab !== tab) return;
            const chartType = meta.chart_type || '';
            if (!chartType) return;
            tabCharts.push({ chartType, widgetData: wd, wid });
        });

        if (tabCharts.length === 0) return;

        // Double rAF — esperar que Alpine muestre el DOM del tab
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                tabCharts.forEach(cw => {
                    const mode = modes[cw.wid] || 'line';
                    ChartRenderer.render(cw.chartType, cw.widgetData, instances, isMulti, 0, mode);
                });
            });
        });

        ctx._renderedTabs.add(tab);
        console.log(`[Lazy] Tab '${tab}': ${tabCharts.length} charts renderizados`);
    },

    /**
     * Hook para llamar al cambiar de tab. Renderiza la tab si no fue renderizada aún.
     * Llamar desde el @click del botón de tab en el template.
     */
    onTabChange(ctx) {
        if (!ctx.hasData) return;
        if (!(ctx._renderedTabs instanceof Set)) ctx._renderedTabs = new Set();
        const tab = ctx.activeTab;
        if (ctx._renderedTabs.has(tab)) return; // ya renderizada
        this._renderTabCharts(ctx, tab);
    }
};
