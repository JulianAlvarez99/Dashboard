/**
 * DateRangeFilter — Controlador de interfaz para el filtro de rango de fechas.
 *
 * Auto-inyectado por Jinja2 cuando DateRangeFilter está activo en la BD.
 * Se registra en window.FilterHandlers['daterange'].
 *
 * Responsabilidades:
 *   1. Inicializar el estado del filtro con valores por defecto (ayer → hoy).
 *   2. Validar coherencia de fechas al cambiar cualquier campo.
 *   3. Corregir automáticamente valores incoherentes (end < start).
 */

'use strict';

window.FilterHandlers = window.FilterHandlers || {};

window.FilterHandlers['daterange'] = {

    /**
     * Se ejecuta cada vez que cambia algún campo del daterange.
     *
     * @param {Object} app    - Instancia de Alpine.js (dashboardApp)
     * @param {Object} value  - El objeto completo {start_date, end_date, start_time, end_time}
     * @param {Object} config - Configuración serializada desde Python (ui_config, required, etc.)
     */
    onChange: function (app, value, config) {
        if (!value || typeof value !== 'object') return;

        // 1. Validar coherencia de fechas: end_date no puede ser anterior a start_date
        if (value.start_date && value.end_date && value.start_date > value.end_date) {
            value.end_date = value.start_date;
            console.warn('[DateRange] end_date era anterior a start_date → corregido automáticamente');
        }

        // 2. Si las fechas son el mismo día, validar que el horario sea coherente
        if (value.start_date === value.end_date && value.start_time && value.end_time) {
            if (value.start_time > value.end_time) {
                value.end_time = value.start_time;
                console.warn('[DateRange] end_time era anterior a start_time (mismo día) → corregido');
            }
        }

        // 3. Actualizar el estado en Alpine para que la UI refleje las correcciones
        app.filterStates['daterange'] = { ...value };

        console.log('[DateRange] Estado actualizado:', value);
    }
};
