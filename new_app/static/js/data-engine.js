/**
 * Dashboard Data Engine (Etapa 3)
 *
 * Pure JavaScript logic for client-side re-aggregation, grouping,
 * and computation of KPI metrics and Chart datasets.
 * Decoupled from Alpine.js state to maintain SRP.
 */

const DashboardDataEngine = {
    /** Parse "HH:MM" string into total minutes since midnight. */
    toMinutes(hhmm) {
        const parts = (hhmm || '00:00').split(':');
        return parseInt(parts[0], 10) * 60 + parseInt(parts[1] || 0, 10);
    },

    /** Convert ISO date-time string to minutes since midnight. */
    dtToMinutes(isoStr) {
        const t = new Date(isoStr);
        return t.getHours() * 60 + t.getMinutes();
    },

    /** Filter detection rows by shift time-window. */
    sliceByShiftWindow(rows, win) {
        const startM = this.toMinutes(win.start);
        const endM = this.toMinutes(win.end);
        const overnight = win.is_overnight || endM <= startM;
        return rows.filter(r => {
            const m = this.dtToMinutes(r.detected_at);
            return overnight ? (m >= startM || m < endM) : (m >= startM && m < endM);
        });
    },

    /** Filter downtime events that overlap with shift time-window. */
    sliceDowntimeByWindow(dt, win) {
        const startM = this.toMinutes(win.start);
        const endM = this.toMinutes(win.end);
        const overnight = win.is_overnight || endM <= startM;
        return dt.filter(d => {
            const sm = this.dtToMinutes(d.start_time);
            const em = this.dtToMinutes(d.end_time);
            if (overnight) {
                return sm >= startM || em < endM;
            }
            return sm < endM && em > startM;  // overlap check
        });
    },

    /** Group rows into time buckets per interval. */
    groupByInterval(rows, interval) {
        const buckets = {};
        rows.forEach(r => {
            const d = new Date(r.detected_at);
            let key;
            switch (interval) {
                case 'minute': key = d.toISOString().slice(0, 16); break;
                case 'hour': key = d.toISOString().slice(0, 13) + ':00'; break;
                case 'day': key = d.toISOString().slice(0, 10); break;
                case 'week': {
                    // ISO week bucket — Monday of the week
                    const day = d.getDay() || 7;
                    const mon = new Date(d); mon.setDate(d.getDate() - day + 1);
                    key = mon.toISOString().slice(0, 10);
                    break;
                }
                default: key = d.toISOString().slice(0, 13) + ':00';
            }
            if (!buckets[key]) buckets[key] = [];
            buckets[key].push(r);
        });
        return buckets;
    },

    /**
     * Central dispatcher: given a widget class name and filtered rows,
     * return the new `data` object, or null if this widget can't be
     * computed client-side.
     */
    recomputeWidget(widgetName, rows, dt, interval, shiftInfo, lineConfig) {
        const output = rows.filter(r => r.area_type === 'output');
        const input = rows.filter(r => r.area_type === 'input');

        switch (widgetName) {
            // ── KPIs ────────────────────────────────────────────────
            case 'KpiTotalProduction':
                return { value: output.length, unit: 'unidades', trend: null };

            case 'KpiTotalWeight': {
                const tw = output.reduce((s, r) => s + (Number(r.product_weight) || 0), 0);
                return { value: Math.round(tw * 100) / 100, unit: 'kg', trend: null };
            }

            case 'KpiTotalDowntime': {
                const td = dt.reduce((s, d) => s + (Number(d.duration) || 0), 0);
                return { value: Math.round(td), unit: 'seg', trend: null };
            }

            case 'KpiAvailability': {
                const planned = shiftInfo ? shiftInfo.planned_seconds : 28800;
                const tdA = dt.reduce((s, d) => s + (Number(d.duration) || 0), 0);
                const avail = planned > 0 ? Math.max(0, (planned - tdA) / planned) : 0;
                return { value: Math.round(avail * 1000) / 10, unit: '%', trend: null };
            }

            case 'KpiPerformance': {
                // Performance = actual / ideal. Ideal = output of reference line config.
                const lineCfgKeys = Object.keys(lineConfig || {});
                const perfFactor = lineCfgKeys.length > 0 ? (lineConfig[lineCfgKeys[0]].performance || 0.9) : 0.9;
                const planned2 = shiftInfo ? shiftInfo.planned_seconds : 28800;
                // Ideal units = performance factor × planned seconds (rough estimate)
                const ideal = perfFactor * (planned2 / 3600) * (output.length > 0 ? (output.length / (planned2 / 3600)) : 0);
                const perf = (ideal > 0 && output.length > 0) ? Math.min(1, output.length / ideal) : perfFactor;
                return { value: Math.round(perf * 1000) / 10, unit: '%', trend: null };
            }

            case 'KpiQuality': {
                const total = input.length + output.length;
                const qual = total > 0 ? output.length / total : 0;
                return { value: Math.round(qual * 1000) / 10, unit: '%', trend: null };
            }

            case 'KpiOee': {
                const plannedO = shiftInfo ? shiftInfo.planned_seconds : 28800;
                const tdO = dt.reduce((s, d) => s + (Number(d.duration) || 0), 0);
                const A = plannedO > 0 ? Math.max(0, (plannedO - tdO) / plannedO) : 0;
                const totalQ = input.length + output.length;
                const Q = totalQ > 0 ? output.length / totalQ : 0;
                const lineCfgO = Object.keys(lineConfig || {});
                const P = lineCfgO.length > 0 ? (lineConfig[lineCfgO[0]].performance || 0.9) : 0.9;
                const oee = A * P * Q;
                return {
                    value: Math.round(oee * 1000) / 10, unit: '%', trend: null,
                    availability: Math.round(A * 1000) / 10,
                    performance: Math.round(P * 1000) / 10,
                    quality: Math.round(Q * 1000) / 10
                };
            }

            // ── Charts ──────────────────────────────────────────────
            case 'ProductionTimeChart': {
                const buckets = this.groupByInterval(output, interval);
                const labels = Object.keys(buckets).sort();
                const values = labels.map(k => buckets[k].length);
                return { labels: labels, datasets: [{ label: 'Producción', data: values }] };
            }

            case 'AreaDetectionChart': {
                const areaMap = {};
                rows.forEach(r => {
                    const k = r.area_id + '__' + (r.area_type || 'unknown');
                    areaMap[k] = (areaMap[k] || { label: r.area_type || String(r.area_id), count: 0 });
                    areaMap[k].count++;
                });
                const areaItems = Object.values(areaMap);
                return {
                    labels: areaItems.map(a => a.label),
                    datasets: [{ label: 'Detecciones', data: areaItems.map(a => a.count) }]
                };
            }

            case 'ProductDistributionChart': {
                const prodMap = {};
                output.forEach(r => {
                    const key = r.product_name || String(r.product_id);
                    prodMap[key] = (prodMap[key] || 0) + 1;
                });
                const prodKeys = Object.keys(prodMap);
                return {
                    labels: prodKeys,
                    datasets: [{ data: prodKeys.map(k => prodMap[k]) }]
                };
            }

            case 'EntryOutputCompareChart': {
                const compareMap = {};
                rows.forEach(r => {
                    const area = r.area_type || 'unknown';
                    compareMap[area] = (compareMap[area] || 0) + 1;
                });
                const compareKeys = Object.keys(compareMap);
                return {
                    labels: compareKeys,
                    datasets: [{ label: 'Detecciones', data: compareKeys.map(k => compareMap[k]) }]
                };
            }

            case 'ScatterChart': {
                const scatterBuckets = this.groupByInterval(rows, interval);
                const scatterLabels = Object.keys(scatterBuckets).sort();
                const scatterData = scatterLabels.map(k => ({ x: k, y: scatterBuckets[k].length }));
                return { labels: scatterLabels, datasets: [{ label: 'Detecciones', data: scatterData }] };
            }

            // ── Table widgets ──────────────────────────────────────
            case 'ProductRanking': {
                const rankMap = {};
                output.forEach(r => {
                    const key = r.product_name || String(r.product_id);
                    if (!rankMap[key]) {
                        rankMap[key] = {
                            product_name: r.product_name || String(r.product_id),
                            product_code: r.product_code || '',
                            product_color: r.product_color || '#999',
                            count: 0, total_weight: 0
                        };
                    }
                    rankMap[key].count++;
                    rankMap[key].total_weight += Number(r.product_weight) || 0;
                });
                const totalOut = output.length;
                const rankRows = Object.values(rankMap).sort((a, b) => b.count - a.count);
                rankRows.forEach(row => {
                    row.total_weight = Math.round(row.total_weight * 100) / 100;
                    row.percentage = totalOut > 0 ? Math.round((row.count / totalOut) * 1000) / 10 : 0;
                });
                return {
                    columns: [
                        { key: 'product_name', label: 'Producto' },
                        { key: 'count', label: 'Cantidad' },
                        { key: 'total_weight', label: 'Peso (kg)' },
                        { key: 'percentage', label: '% del Total' },
                    ],
                    rows: rankRows,
                    total_production: totalOut,
                };
            }

            case 'DowntimeTable': {
                const dtRows = dt.map(d => ({
                    start_time: d.start_time,
                    end_time: d.end_time,
                    duration: Math.round(Number(d.duration) || 0),
                    reason_code: d.reason_code || '',
                    source: d.source || 'calculated',
                }));
                return { rows: dtRows, total_downtime: dtRows.reduce((s, r) => s + r.duration, 0) };
            }

            default: return null;
        }
    }
};
