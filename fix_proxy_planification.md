Planificación: eliminar el proxy get params()
Contexto del impacto
Todos los usos de ctx.params / this.params relevados:
ArchivoUsoTipo de accesodashboard-orchestrator.jsthis._normalizeParams(ctx.params)Pasa el objeto completodashboard-orchestrator.jsctx.params.shift_idLectura de clavedashboard-orchestrator.jsctx.params.product_idsLectura de clavedashboard-orchestrator.jsctx.params.intervalLectura de clavejs_inline filters (ShiftFilter, ProductFilter, IntervalFilter)this.filterStates[x]Ya usan filterStates directamente ✓CurveTypeFilter js_inlinethis.filterStates['curve_type']Ya usa filterStates directamente ✓
Los js_inline de los filtros ya están bien — no usan params. Los tres cambios reales son todos en dashboard-orchestrator.js más la eliminación del getter en dashboard-app.js.

Paso 1 — Refactorizar _normalizeParams en dashboard-orchestrator.js
Cambiar la firma para que reciba filterStates directamente y construya el objeto plano internamente, eliminando la dependencia del proxy:
javascript// ANTES:
_normalizeParams(params) {
    const out = JSON.parse(JSON.stringify(params));
    for (let k in out) {
        if (k === 'daterange') continue;
        if (out[k] === '') out[k] = null;
    }
    return out;
},

// DESPUÉS:
_normalizeParams(filterStates) {
    const out = {};
    for (const [key, fs] of Object.entries(filterStates)) {
        const v = fs.value;
        out[key] = (key !== 'daterange' && v === '') ? null : v;
    }
    return out;
},
Y actualizar el único llamador en applyFilters:
javascript// ANTES:
const normalizedParams = this._normalizeParams(ctx.params);

// DESPUÉS:
const normalizedParams = this._normalizeParams(ctx.filterStates);

Paso 2 — Refactorizar recomputeFromRaw en dashboard-orchestrator.js
Reemplazar los tres accesos a ctx.params por accesos directos a ctx.filterStates:
javascript// ANTES:
const shiftId = ctx.params.shift_id ? String(ctx.params.shift_id) : null;
const pids = (ctx.params.product_ids || []).map(Number);
const interval = ctx.params.interval || 'hour';

// DESPUÉS:
const shiftId = ctx.filterStates['shift_id']?.value
    ? String(ctx.filterStates['shift_id'].value) : null;
const pids = (ctx.filterStates['product_ids']?.value || []).map(Number);
const interval = ctx.filterStates['interval']?.value || 'hour';

Paso 3 — Eliminar el getter en dashboard-app.js
Eliminar el bloque completo del proxy y su comentario:
javascript// ELIMINAR todo este bloque:
// ── Backward-compatible proxy: params.X reads still work ──
// Write via: this.filterStates['X'].value = newValue
get params() {
    const p = {};
    for (const [key, fs] of Object.entries(this.filterStates)) {
        p[key] = fs.value;
    }
    return p;
},

Paso 4 — Verificación
Buscar en todos los archivos JS cualquier referencia remanente a ctx.params o this.params que no haya sido migrada:

dashboard-orchestrator.js → debe quedar sin ninguna referencia a ctx.params
dashboard-app.js → getter eliminado
dashboard-events.js → no usa params, sin cambios
Archivos js_inline de filtros → ya usan filterStates directamente, sin cambios


Orden de ejecución recomendado
Hacer los pasos 1 y 2 juntos en dashboard-orchestrator.js en un solo commit, y el paso 3 en el mismo commit. Si el proxy se elimina antes de migrar los consumidores, el runtime tira error silencioso en Alpine.
El cambio no tiene impacto en el backend ni en los templates Jinja. Solo afecta los dos archivos JS mencionados.