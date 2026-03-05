"""
HighlightPeaksFilter — Toggle to highlight production peaks in charts.

Not a SQL filter — 100% client-side, self-contained in js_inline.
When active, peaks are painted in amber accent; non-peak data is shown
at 25% opacity (dimmed but still visible). On disable the chart is fully
restored to its original state.
"""
from __future__ import annotations

from typing import Any, Optional

from new_app.services.filters.base import InputFilter


class HighlightPeaksFilter(InputFilter):
    """Toggle to highlight production peaks in line_chart and bar_chart widgets."""

    filter_type    = "toggle"
    param_name     = "highlight_peaks"
    options_source = None
    default_value  = False
    placeholder    = None
    required       = False
    depends_on     = None
    ui_config      = {"label": "Resaltar picos"}

    # ── Frontend contract ────────────────────────────
    pydantic_type = "bool"
    js_behavior   = {
        "serialize":  "bool",
        "include_if": "not_null",
        "on_change":  "onHighlightPeaksChange",
    }
    js_inline = """\
    onHighlightPeaksChange() {
        if (!this.hasData) return;
        const self = this;

        // ── Register a ONE-TIME $watch so any chart re-render (tab switch,
        //    line↔bar toggle) re-applies the highlight automatically ────────
        if (!self._pkWatcherRegistered) {
            self._pkWatcherRegistered = true;
            self.$watch('chartInstances', () => {
                if (!!(self.filterStates['highlight_peaks']?.value)) {
                    // Stale snapshots belong to the old Chart instances — discard.
                    self._pkSnapshots = {};
                    // Double rAF: let ChartRenderer finish drawing before styling
                    requestAnimationFrame(() => requestAnimationFrame(() => {
                        self.onHighlightPeaksChange();
                    }));
                }
            });
        }

        const enabled = !!(self.filterStates['highlight_peaks']?.value);
        const instances = self.chartInstances;

        const PEAK_COLOR  = 'rgba(251,191,36,1)';
        const PEAK_BORDER = 'rgba(255,255,255,0.9)';
        const DIM_ALPHA   = 0.2;

        function dimColor(color, alpha) {
            if (!color || typeof color !== 'string') return `rgba(150,150,150,${alpha})`;
            const m = color.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
            if (m) return `rgba(${m[1]},${m[2]},${m[3]},${alpha})`;
            const h = color.match(/^#([0-9a-f]{3,8})$/i);
            if (h) {
                let hx = h[1];
                if (hx.length === 3) hx = hx.split('').map(c => c + c).join('');
                return `rgba(${parseInt(hx.slice(0,2),16)},${parseInt(hx.slice(2,4),16)},${parseInt(hx.slice(4,6),16)},${alpha})`;
            }
            return `rgba(150,150,150,${alpha})`;
        }

        function resolveColor(val) {
            if (Array.isArray(val)) { for (const c of val) { if (typeof c === 'string') return c; } return null; }
            return typeof val === 'string' ? val : null;
        }

        function maxIndex(values) {
            let best = -Infinity, idx = -1;
            values.forEach((v, i) => { if (v != null && Number(v) > best) { best = Number(v); idx = i; } });
            return idx;
        }

        if (!self._pkSnapshots) self._pkSnapshots = {};

        Object.keys(instances).forEach(canvasId => {
            let chart = (typeof Alpine !== 'undefined' && Alpine.raw)
                ? Alpine.raw(instances[canvasId]) : instances[canvasId];
            if (!chart) return;
            const chartType = chart.config.type;
            if (chartType !== 'line' && chartType !== 'bar') return;

            if (enabled) {
                // Snapshot the CURRENT (original) dataset styles exactly once per chart
                if (!self._pkSnapshots[canvasId]) {
                    self._pkSnapshots[canvasId] = chart.data.datasets.map(ds => ({
                        backgroundColor:      ds.backgroundColor,
                        borderColor:          ds.borderColor,
                        pointBackgroundColor: ds.pointBackgroundColor,
                        pointBorderColor:     ds.pointBorderColor,
                        pointRadius:          ds.pointRadius,
                        pointBorderWidth:     ds.pointBorderWidth,
                    }));
                }

                chart.data.datasets.forEach((ds, idx) => {
                    const values  = ds.data || [];
                    const peakIdx = maxIndex(values);
                    const snap    = self._pkSnapshots[canvasId][idx];
                    const srcColor = resolveColor(snap.borderColor)
                                  || resolveColor(snap.backgroundColor)
                                  || 'rgba(99,102,241,1)';

                    if (chartType === 'line') {
                        ds.borderColor          = dimColor(srcColor, DIM_ALPHA);
                        ds.pointBackgroundColor = values.map((_, i) =>
                            i === peakIdx ? PEAK_COLOR : dimColor(srcColor, DIM_ALPHA));
                        ds.pointBorderColor     = values.map((_, i) =>
                            i === peakIdx ? PEAK_BORDER : 'transparent');
                        ds.pointRadius          = values.map((_, i) => i === peakIdx ? 10 : 2);
                        ds.pointBorderWidth     = values.map((_, i) => i === peakIdx ? 2 : 0);
                    } else {
                        ds.backgroundColor = values.map((v, i) =>
                            i === peakIdx
                                ? PEAK_COLOR
                                : dimColor(Array.isArray(snap.backgroundColor) ? snap.backgroundColor[i] : srcColor, DIM_ALPHA));
                    }
                });

                // rAF ensures Chart.js actually repaints (not just marks dirty)
                requestAnimationFrame(() => chart.update());

            } else {
                const snap = self._pkSnapshots[canvasId];
                if (!snap) return;

                chart.data.datasets.forEach((ds, idx) => {
                    const s = snap[idx];
                    if (!s) return;
                    ['backgroundColor', 'borderColor',
                     'pointBackgroundColor', 'pointBorderColor',
                     'pointRadius', 'pointBorderWidth',
                    ].forEach(prop => {
                        if (s[prop] !== undefined) ds[prop] = s[prop];
                        else delete ds[prop];
                    });
                });

                delete self._pkSnapshots[canvasId];
                requestAnimationFrame(() => chart.update());
            }
        });
    }"""
    js_validation = None

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        return isinstance(value, bool)

    def get_default(self) -> bool:
        return bool(self.config.default_value) if self.config.default_value is not None else False

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        # Peak highlight is a visual effect — does not modify SQL queries
        return None

