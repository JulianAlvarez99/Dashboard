/**
 * Dashboard Orchestrator
 *
 * Handles the complex multi-step processes of the dashboard:
 * 1. Fetching data and updating Alpine.js state (applyFilters)
 * 2. Re-computing data client-side (recomputeFromRaw)
 * 3. Rendering all charts (renderAllCharts)
 */

// ── Serialization helpers (used by _buildRequestBody) ─────────────

/**
 * Determine whether a filter value should be included in the request body.
 * @param {*} value
 * @param {string} includeIf  - 'always' | 'not_null' | 'truthy' | 'array_not_empty'
 */
function _shouldInclude(value, includeIf) {
    switch (includeIf) {
        case 'always':          return true;
        case 'not_null':        return value !== null && value !== undefined;
        case 'array_not_empty': return Array.isArray(value) && value.length > 0;
        case 'truthy':
        default:                return !!value;
    }
}

/**
 * Serialize a filter value to the wire format.
 * @param {*} value
 * @param {string} serialize  - 'int' | 'str' | 'bool' | 'array_int' | 'array_str' | 'daterange' | 'line_id' | 'raw'
 * @param {Object} ctx        - Alpine context (unused here but available for extensions)
 */
function _serializeValue(value, serialize, ctx) {
    switch (serialize) {
        case 'int':        return parseInt(value);
        case 'str':        return String(value);
        case 'bool':       return Boolean(value);
        case 'array_int':  return Array.isArray(value) ? value.map(Number) : [Number(value)];
        case 'array_str':  return Array.isArray(value) ? value.map(String) : [String(value)];
        case 'daterange':  return value;           // object {start_date,...} as-is
        case 'line_id': {
            if (value === null || value === undefined) return undefined;
            const _n = parseInt(value);
            return isNaN(_n) ? String(value) : _n;
        }
        case 'not_null':   return value;
        case 'raw':
        default:           return value;
    }
}

// ── ──────────────────────────────────────────────────────────────

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
            const normalizedParams = this._normalizeParams(ctx.filterStates);
            const valResult = this._validateParamsLocally(normalizedParams, ctx.filterStates);

            if (!valResult.valid) {
                console.warn('[Filters] Validation errors:', valResult.errors);
                this._showFilterError(valResult.errors);
                ctx.loading = false;
                return;
            }

            ctx.sidebarOpen = false;

            const body = this._buildRequestBody(ctx);
            console.log('[DEBUG] Request body:', JSON.stringify(body, null, 2));
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

            ctx.filterCount = this._countActiveFilters(ctx.filterStates);
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

        const shiftId = ctx.filterStates['shift_id']?.value
            ? String(ctx.filterStates['shift_id'].value) : null;
        if (shiftId && ctx._shiftWindows[shiftId]) {
            const win = ctx._shiftWindows[shiftId];
            rows = DashboardDataEngine.sliceByShiftWindow(rows, win);
            dt = DashboardDataEngine.sliceDowntimeByWindow(dt, win);
        }

        const pids = (ctx.filterStates['product_ids']?.value || []).map(Number);
        if (pids.length > 0) {
            rows = rows.filter(r => pids.indexOf(Number(r.product_id)) !== -1);
        }

        const interval = ctx.filterStates['interval']?.value || 'hour';
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

    _normalizeParams(filterStates) {
        const out = {};
        for (const [key, fs] of Object.entries(filterStates)) {
            const v = fs.value;
            out[key] = (key !== 'daterange' && v === '') ? null : v;
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
    _validateParamsLocally(params, filterStates) {
        const errors = {};

        for (const [param, fstate] of Object.entries(filterStates)) {
            const rules = fstate.validation;
            if (!rules) continue;

            const val = params[param];

            // type: daterange — multi-field object validation
            if (rules.type === 'daterange') {
                const dr = val;
                if (!dr || typeof dr !== 'object') {
                    errors[param] = 'El rango de fechas es obligatorio';
                } else if (!dr.start_date || !/^\d{4}-\d{2}-\d{2}$/.test(dr.start_date)) {
                    errors[param] = 'Fecha de inicio inválida (formato YYYY-MM-DD)';
                } else if (!dr.end_date || !/^\d{4}-\d{2}-\d{2}$/.test(dr.end_date)) {
                    errors[param] = 'Fecha de fin inválida (formato YYYY-MM-DD)';
                } else if (dr.start_date > dr.end_date) {
                    errors[param] = 'La fecha de inicio debe ser anterior a la fecha de fin';
                }
                continue;
            }
            // required check
            if (rules.required) {
                if (val === null || val === undefined || val === '') {
                    errors[param] = rules.required_msg || `El campo ${param} es obligatorio`;
                    continue;
                }
            }
            if (val === null || val === undefined) continue;

            // enum check
            if (rules.enum && !rules.enum.includes(val)) {
                errors[param] = rules.enum_msg || `Valor inválido: ${val}`;
            }
            // min (number)
            if (rules.min !== undefined) {
                const parsed = Number(val);
                if (isNaN(parsed) || parsed < rules.min) {
                    errors[param] = rules.min_msg || `Debe ser un número mayor o igual a ${rules.min}`;
                }
            }
        }

        return {
            valid: Object.keys(errors).length === 0,
            errors,
        };
    },

    _countActiveFilters(filterStates) {
        let count = 0;
        for (const [key, fstate] of Object.entries(filterStates)) {
            const v = fstate.value;
            if (v !== null && v !== '' && v !== false &&
                !(Array.isArray(v) && v.length === 0)) count++;
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
        const body = { include_raw: true };

        for (const [param, fstate] of Object.entries(ctx.filterStates)) {
            try {
                const val    = fstate.value;
                const should = _shouldInclude(val, fstate.include_if);
                if (!should) continue;

                const serialized = _serializeValue(val, fstate.serialize, ctx);
                if (serialized === undefined) continue;

                // line_id with group value expands to line_ids
                if (param === 'line_id') {
                    const lineOpt = ctx._lineOptions.find(
                        o => String(o.value) === String(val)
                    );
                    if (lineOpt && lineOpt.extra && lineOpt.extra.is_group) {
                        // Send both: line_id for validation, line_ids for query
                        body.line_id = val;  // "all" or "group_X"
                        body.line_ids = lineOpt.extra.line_ids.join(',');
                    } else if (serialized !== undefined) {
                        body.line_id = serialized;
                    }
                } else if (param === 'daterange') {
                    // daterange is a nested object — send as-is
                    body.daterange = val;
                } else {
                    body[param] = serialized;
                }
            } catch (e) {
                console.error('[buildRequestBody] Error on param', param, e);
            }
        }

        // Multi-line group override (isMultiLine set by onLineChange)
        if (ctx.isMultiLine && ctx.selectedLineGroup) {
            // Keep line_id for backend validation, override line_ids
            body.line_ids = ctx.selectedLineGroup.join(',');
        }

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

            const widgetName = meta.widget_name;
            const chartType = meta.chart_type || '';

            // ── Check new registry first, fall back to chart_type ──
            const hasBuilder = typeof WidgetChartBuilders !== 'undefined'
                               && !!WidgetChartBuilders[widgetName];
            const isChart = hasBuilder || !!chartType;
            if (!isChart) return;

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
