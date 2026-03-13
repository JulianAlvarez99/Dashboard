/**
 * ShiftFilter — JS handler for the shift dropdown.
 */

'use strict';

window.FilterHandlers = window.FilterHandlers || {};

// 'shift_id' COINCIDE con param_name en Python
window.FilterHandlers['shift_id'] = {
    /**
     * @param {Object} app - La instancia actual de Alpine.js
     * @param {Any} value - El valor seleccionado
     * @param {Object} config - Configuración serializada del filtro
     */
    onChange: function(app, value, config) {
        console.log(`[ShiftFilter] Valor actualizado a:`, value);
        
        const option = config.options.find(
            o => String(o.value) === String(value)
        );
        
        if (option) {
            console.log(`[ShiftFilter] Turno seleccionado: ${option.label}`);
            
            // 1. Si no hay datos crudos cargados aún, no hacemos nada.
            if (!app.rawData || app.rawData.length === 0) {
                return;
            }

            // 2. Si se selecciona "all", mostramos todos los datos devuelta
            if (value === 'all') {
                app.filteredData = [...app.rawData];
                console.log(`[ShiftFilter] Reseteado filtro local: mostrando todos los ${app.filteredData.length} registros.`);
                return;
            }

            // 3. Extraemos horas del turno de option.extra
            const startTimeStr = option.extra.start_time; // Ej: "06:00:00"
            const endTimeStr = option.extra.end_time;     // Ej: "14:00:00"
            const isOvernight = option.extra.is_overnight;

            if (!startTimeStr || !endTimeStr) {
                console.warn("[ShiftFilter] Faltan horarios en la configuración del turno");
                return;
            }

            // Convertimos 'HH:MM:SS' a minutos desde las 00:00 para hacer fácil la comparación
            const toMinutes = (timeStr) => {
                const parts = timeStr.split(':');
                return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
            };

            const startMin = toMinutes(startTimeStr);
            const endMin = toMinutes(endTimeStr);

            // 4. Filtrar localmente iterando sobre app.rawData
            app.filteredData = app.rawData.filter(row => {
                // Asumimos que row.detected_at viene algo como "2026-03-01 08:15:30" (string ISO o SQL)
                // Extraemos solo la parte del tiempo "08:15:30" 
                const dateObj = new Date(row.detected_at);
                const rowMin = dateObj.getHours() * 60 + dateObj.getMinutes();

                if (isOvernight) {
                    // Si el turno cruza medianoche (Ej: 22:00 a 06:00), el horario debe ser:
                    // MAYOR a 22:00  O  MENOR a 06:00
                    return rowMin >= startMin || rowMin <= endMin;
                } else {
                    // Turno normal (Ej: 06:00 a 14:00)
                    // MAYOR a 06:00 Y MENOR a 14:00
                    return rowMin >= startMin && rowMin <= endMin;
                }
            });

            console.log(`[ShiftFilter] Filtrado local aplicado: ${app.filteredData.length} resultados filtrados de ${app.rawData.length} totales.`);
            
        } else {
            console.log(`[ShiftFilter] Turno no encontrado para el valor: ${value}`);
        }
    }
};
