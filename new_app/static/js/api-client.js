/**
 * Dashboard API Client
 * 
 * Centralizes all fetch operations for the Dashboard, abstracting
 * endpoints, method handling, and basic error throwing away from the UI state.
 *
 * Authentication: reads the JWT bearer token from
 *   <meta name="api-token" content="<token>">
 * and sends it as  Authorization: Bearer <token>  on every request.
 */

/**
 * Read the JWT access token embedded by Flask in a <meta> tag.
 * Returns an empty string if no token is present (unauthenticated page).
 *
 * @returns {string}
 */
function _getApiToken() {
    const meta = document.querySelector('meta[name="api-token"]');
    return meta ? meta.content : '';
}

/**
 * Build fetch headers, injecting the Authorization header when a token exists.
 *
 * @param {Object} extra  Additional headers to merge.
 * @returns {Object}
 */
function _apiHeaders(extra = {}) {
    const headers = { 'Content-Type': 'application/json', ...extra };
    const token = _getApiToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

const DashboardAPI = {
    /**
     * Validate filter states against backend validation schemas.
     * Empty string parameters are treated as null per Pydantic needs.
     * 
     * @param {string} apiBase 
     * @param {Object} params 
     * @returns {Promise<Object>} The validation result {valid: boolean, errors?: Object}
     */
    async validateFilters(apiBase, params) {
        const response = await fetch(`${apiBase}/api/v1/filters/validate`, {
            method: 'POST',
            headers: _apiHeaders(),
            body: JSON.stringify(params),
        });
        return response.json();
    },

    /**
     * Fetch available Area options for a specific line ID.
     * 
     * @param {string} apiBase 
     * @param {string|number} lineId 
     * @returns {Promise<Array>} List of area options
     */
    async fetchAreas(apiBase, lineId) {
        const response = await fetch(`${apiBase}/api/v1/filters/areas?line_id=${lineId}`, {
            headers: _apiHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch areas for line');
        return response.json();
    },

    /**
     * Fetch primary dashboard data payload including widgets and raw data limits.
     * 
     * @param {string} dashboardApiUrl 
     * @param {Object} body
     * @returns {Promise<Object>} Structured result containing raw_data, metadata, widgets
     */
    async fetchDashboardData(dashboardApiUrl, body) {
        const response = await fetch(dashboardApiUrl, {
            method: 'POST',
            headers: _apiHeaders(),
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }
};

