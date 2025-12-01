/**
 * Módulo encargado de la comunicación con el Backend (API).
 * Maneja las peticiones HTTP y la gestión de errores de red.
 */

/**
 * Realiza una petición al endpoint del dashboard con los filtros proporcionados.
 * Nota: Para filtros complejos, se recomienda usar fetch directo en el controlador,
 * pero esta función es útil para llamadas estándar.
 * * @param {string} interval - Intervalo de agrupación (ej: '1h', '15min').
 * @param {string|null} startDate - Fecha inicio ISO (opcional).
 * @param {string|null} endDate - Fecha fin ISO (opcional).
 * @returns {Promise<Object>} - Promesa con los datos JSON del dashboard.
 * @throws {Error} - Si la respuesta HTTP no es ok.
 */
export async function fetchDashboardData(interval, startDate = null, endDate = null) {
    try {
        // Construcción de URL base
        // let url = `/centralnorte/api/dashboard?interval=${interval}`; // Habilitar si se prueba hosting
        let url = `/api/dashboard?interval=${interval}`; // Habilitar si se prueba local
        
        // Append de parámetros opcionales
        if (startDate) url += `&start=${startDate}`;
        if (endDate) url += `&end=${endDate}`;

        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Error HTTP: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error("Error en API Service:", error);
        throw error; // Re-lanzamos para manejo en la capa superior (UI)
    }
}