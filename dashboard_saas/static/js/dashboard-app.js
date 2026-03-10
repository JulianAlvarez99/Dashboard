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
    // Retornamos el objeto principal que definirá el estado de Alpine.js para x-data="dashboardApp()"
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

        // ── INIT: Secuencia de arranque inicial ─────────────────

        init() {
            // 1. Leemos la configuración inyectada por el servidor (Flask) en el DOM
            // Esto permite que el backend pase datos seguros (URL de APIs, lista de filtros, widgets)
            const configEl = document.getElementById('dashboard-config');
            if (configEl) {
                try {
                    const config = JSON.parse(configEl.textContent);
                    this.apiBase = config.apiBase || '';
                    this.filters = config.filters || [];
                    this.widgets = config.widgets || [];
                } catch (e) {
                    console.error('[Dashboard] Error al parsear la configuración del servidor:', e);
                }
            }

            // 2. Inicializar los estados de los filtros dinámicamente
            // Recorremos los filtros que vinieron de base de datos y les asignamos su valor por defecto
            this.filters.forEach(filter => {
                this.filterStates[filter.param_name] = filter.default_value ?? '';
            });

            console.log('[Dashboard] Inicialización exitosa. Filtros descubiertos:', this.filters.length, '| Widgets descubiertos:', this.widgets.length);

            // 3. Renderizar íconos de Lucide
            // Usamos $nextTick para asegurarnos de que Alpine termine de dibujar el HTML antes de buscar los íconos
            this.$nextTick(() => {
                if (window.lucide) lucide.createIcons();
            });
        },

        // ── MANEJADOR: Cambios en Filtros ───────────────────────

        onFilterChange(paramName, value) {
            // 1. Actualizar el estado interno del componente
            this.filterStates[paramName] = value;

            // 2. Delegar lógica específica a manejadores externos si existen
            // Permite mantener código modular: Cada filtro puede tener su archivo .js con lógica propia (ej: ocultar/mostrar cosas)
            const handler = window.FilterHandlers && window.FilterHandlers[paramName];
            if (handler && handler.onChange) {
                const filter = this.filters.find(f => f.param_name === paramName);
                handler.onChange(this, value, filter); // Le pasamos la app entera (this)
            }

            console.log(`[Dashboard] Cambio detectado en filtro: ${paramName} = ${value}`);
        },

        // ── ACCIÓN: Aplicar Filtros (Pipeline Principal) ────────

        async applyFilters() {
            // 1. Validación preventiva en el frontend
            // Recorremos dinámicamente todos los filtros que vinieron marcados como "required"
            // y chequeamos que tengan un valor válido antes de enviar el payload al backend.
            for (const filter of this.filters) {
                if (!filter.required) continue;

                const val = this.filterStates[filter.param_name];

                // Para objetos complejos (daterange) validamos que no esté vacío internamente
                if (typeof val === 'object' && val !== null) {
                    const hasContent = Object.values(val).some(v => v !== '' && v !== null && v !== undefined);
                    if (!hasContent) {
                        alert(`Completá el filtro obligatorio: ${filter.description || filter.filter_name}`);
                        return;
                    }
                } else {
                    // Para valores simples (string, number)
                    if (!val && val !== 0 && val !== false) {
                        alert(`Completá el filtro obligatorio: ${filter.description || filter.filter_name}`);
                        return;
                    }
                }
            }

            // 2. Limpiar estados previos y mostrar icono de carga
            this.loading = true;
            this.rawData = [];
            this.lastQueryInfo = null;

            try {
                // 3. Empaquetar solo los filtros que tienen un valor asignado (ignorar nulos o vacíos)
                const payload = {};
                for (const [key, value] of Object.entries(this.filterStates)) {
                    if (value !== '' && value !== null && value !== undefined) {
                        payload[key] = value;
                    }
                }

                console.log('[Dashboard] Payload a enviar para aplicar filtros:', payload);

                // 4. Realizar la petición POST asíncrona hacia FastAPI
                const response = await fetch(`${this.apiBase}/api/v1/dashboard/apply-filters`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filters: payload }),
                });

                // 5. Manejo de Errores (Si FastAPI devuelve Status 400 o 500 lanza excepción)
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || `Error HTTP: ${response.status}`);
                }

                // 6. Extraer resultados procesados
                const result = await response.json();

                // 7. Actualizar el estado con la información recibida (Tablas y Rows en crudo)
                this.rawData = result.data || [];
                this.lastQueryInfo = {
                    row_count: result.row_count,
                    tables_queried: result.tables_queried,
                    query: result.query,           // SQL final construido por QueryBuilder
                    params: result.params,         // Diccionario de variables amarradas al SQL
                };

                console.log(`[Dashboard] Resumen de consulta: ${result.row_count} filas devueltas leyendo desde [${result.tables_queried.join(', ')}]`);

            } catch (err) {
                console.error('[Dashboard] Falló la aplicación de filtros:', err);
                alert('Error al consultar datos: ' + err.message);
            } finally {
                // 8. Ocultar indicador de carga sin importar si la petición fue exitosa o falló
                this.loading = false;
            }
        },
    };
}
