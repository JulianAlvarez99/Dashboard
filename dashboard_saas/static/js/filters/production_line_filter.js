/**
 * ProductionLineFilter — JS handler for the production line dropdown.
 *
 * Handles:
 * - Line change events (individual vs group selection)
 * - Storing the selected line value and metadata
 *
 * This file is auto-loaded by the template when the filter is active.
 */

'use strict';

// Register this filter's handler in the global FilterHandlers registry
window.FilterHandlers = window.FilterHandlers || {};

window.FilterHandlers['line_id'] = {

    /**
     * Called when the user selects a different line option.
     *
     * @param {object} context - The Alpine.js component (dashboardApp)
     * @param {string} value - The selected option value
     * @param {object} filter - The filter config from the server
     */
    onChange(context, value, filter) {
        // Find the matching option in the filter's options list
        const option = filter.options.find(
            o => String(o.value) === String(value)
        );

        if (!option) {
            console.log('[LineFilter] No option found for value:', value);
            return;
        }

        const extra = option.extra || {};

        if (extra.is_group) {
            // Group selected (e.g. "Todas las líneas" or a predefined group)
            context.selectedLineInfo = {
                isGroup: true,
                lineIds: extra.line_ids,
                label: option.label,
            };
            console.log('[LineFilter] Group selected:', option.label, '→ lines', extra.line_ids);
        } else {
            // Individual line selected
            context.selectedLineInfo = {
                isGroup: false,
                lineId: value,
                lineCode: extra.line_code,
                label: option.label,
                downtimeThreshold: extra.downtime_threshold,
            };
            console.log('[LineFilter] Line selected:', option.label, '(code:', extra.line_code, ')');
        }
    }
};
