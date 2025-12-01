/* static/js/main.js */

import { renderProductionChart, renderComparisonChart, renderProductPieChart } from './charts.js';
import { updateKPIs, renderDowntimeTable, renderSummaryTable, updateLastUpdatedTime, showLoading } from './ui.js';

// Globales
let currentPdfBlobUrl = null;
let pdfModalInstance = null;

// Configuración Global en memoria (Estructura Dual)
let globalUiSettings = {
    'card-evolution':    {'admin': true, 'client': true},
    'card-balance':      {'admin': true, 'client': true},
    'card-distribution': {'admin': true, 'client': true},
    'card-downtime':     {'admin': true, 'client': true}
};

document.addEventListener('DOMContentLoaded', () => {
    loadProducts(); 
    setupEventListeners();
    setInitialDefaults();
    setupDateConstraints();
    fetchAndApplySettings();

    const modalEl = document.getElementById('pdfModal');
    if (modalEl) {
        pdfModalInstance = new bootstrap.Modal(modalEl);
    }
});

// --- GESTIÓN DE CONFIGURACIÓN GLOBAL ---

/**
 * Obtiene la configuración desde el servidor y actualiza la UI
 */
async function fetchAndApplySettings() {
    try {
        const response = await fetch(window.API_URLS.settings);
        if (response.ok) {
            globalUiSettings = await response.json();
            
            // Actualizar estado de los checkboxes (Solo visual para Admin)
            document.querySelectorAll('.visibility-check').forEach(check => {
                const targetCard = check.dataset.target; // "card-evolution"
                const targetRole = check.dataset.role;   // "admin" o "client"
                
                if (globalUiSettings[targetCard] && globalUiSettings[targetCard].hasOwnProperty(targetRole)) {
                    check.checked = globalUiSettings[targetCard][targetRole];
                }
            });
            
            applyVisibilityRules();
        }
    } catch (e) {
        console.error("Error cargando configuración UI:", e);
    }
}

/**
 * Envía la nueva configuración al servidor (Solo Admin)
 * Lee los checkboxes dobles y construye el objeto de configuración.
 */
async function saveSettingsToServer() {
    // Reconstruimos el objeto settings basado en el DOM
    const newSettings = {
        'card-evolution':    {'admin': true, 'client': true},
        'card-balance':      {'admin': true, 'client': true},
        'card-distribution': {'admin': true, 'client': true},
        'card-downtime':     {'admin': true, 'client': true}
    };

    document.querySelectorAll('.visibility-check').forEach(check => {
        const targetCard = check.dataset.target;
        const targetRole = check.dataset.role;
        newSettings[targetCard][targetRole] = check.checked;
    });

    try {
        const response = await fetch(window.API_URLS.settings, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newSettings)
        });
        
        if (response.ok) {
            globalUiSettings = newSettings;
            applyVisibilityRules();
        } else {
            const err = await response.json();
            alert("Error al guardar configuración: " + (err.error || "Desconocido"));
            fetchAndApplySettings(); // Revertir visualmente
        }
    } catch (e) {
        console.error("Error guardando settings:", e);
    }
}

/**
 * Aplica las reglas de visibilidad.
 * Determina qué ver basándose en window.CURRENT_USER_ROLE
 */
function applyVisibilityRules() {
    // El rol del usuario actual ('admin' o 'client')
    const userRole = window.CURRENT_USER_ROLE || 'client';
    
    // Verificamos si estamos viendo "Todas las líneas"
    // Si estamos en ALL, forzamos ocultar datos de paradas
    const lineSelect = document.getElementById('line-select');
    const isAllLines = lineSelect && lineSelect.value === 'ALL';

    for (const [cardId, rolesConfig] of Object.entries(globalUiSettings)) {
        const container = document.getElementById(cardId);
        if (container) {
            let shouldShow = rolesConfig[userRole]; // True/False según config

            // REGLA DE NEGOCIO: Si es tarjeta de paradas y estamos en ALL, ocultar SIEMPRE
            if (cardId === 'card-downtime' && isAllLines) {
                shouldShow = false;
            }

            container.style.display = shouldShow ? 'block' : 'none';
        }
    }

    // APLICAR REGLA DE "TODAS LAS LÍNEAS" A LOS KPIs DE PARADAS TAMBIÉN
    const kpiCount = document.getElementById('kpi-card-downtime-count');
    const kpiTime = document.getElementById('kpi-card-downtime-time');
    
    if (kpiCount) kpiCount.style.display = isAllLines ? 'none' : 'block';
    if (kpiTime) kpiTime.style.display = isAllLines ? 'none' : 'block';
}

// ----------------------------------------

async function loadProducts() {
    try {
        const response = await fetch(window.API_URLS.products);
        const products = await response.json();
        const select = document.getElementById('product-select');
        select.innerHTML = '<option value="ALL">Todos</option>';
        products.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.text = p.name;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Error cargando productos", e);
    }
}

function setupEventListeners() {
    document.getElementById('btn-filter').addEventListener('click', applyFilters);
    document.getElementById('btn-pdf').addEventListener('click', openPDFModal);
    
    document.getElementById('btn-refresh-preview').addEventListener('click', generatePDFPreview);
    document.getElementById('btn-download-final').addEventListener('click', downloadGeneratedPDF);
    
    // Listener para los checkboxes de configuración (Solo Admin)
    document.querySelectorAll('.visibility-check').forEach(check => {
        check.addEventListener('change', saveSettingsToServer);
    });
}

function setInitialDefaults() {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    document.getElementById('date-start').value = yesterday.toISOString().split('T')[0];
    document.getElementById('time-start').value = "06:00";
    document.getElementById('date-end').value = now.toISOString().split('T')[0];
    document.getElementById('time-end').value = "06:00";
    document.getElementById('interval-select').value = '1h';
    document.getElementById('line-select').value = 'ALL';
    document.getElementById('product-select').value = 'ALL';
    document.getElementById('curve-type').value = 'stepped'; 
    document.getElementById('show-stops-check').checked = false;
}

// --- FUNCIONES PDF ---
function openPDFModal() {
    if (pdfModalInstance) pdfModalInstance.show();
    generatePDFPreview();
}

function generatePDFPreview() {
    const element = document.getElementById('dashboard-content');
    const iframe = document.getElementById('pdf-preview-frame');
    const spinner = document.getElementById('pdf-loading-spinner');
    spinner.style.display = 'block';
    iframe.style.opacity = '0.3';
    const format = document.getElementById('pdf-format').value;
    const orientation = document.getElementById('pdf-orientation').value;
    const opt = {
        margin: [5, 5, 5, 5],
        filename: 'preview.pdf',
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false, allowTaint: true },
        jsPDF: { unit: 'mm', format: format, orientation: orientation },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
    };
    document.body.classList.add('generating-pdf');
    html2pdf().set(opt).from(element).output('bloburl')
        .then(function(pdfUrl) {
            currentPdfBlobUrl = pdfUrl;
            iframe.src = pdfUrl;
            document.body.classList.remove('generating-pdf');
            spinner.style.display = 'none';
            iframe.style.opacity = '1';
        })
        .catch(err => {
            console.error("Error PDF:", err);
            document.body.classList.remove('generating-pdf');
            spinner.style.display = 'none';
            alert("Error generando la vista previa.");
        });
}

function downloadGeneratedPDF() {
    if (!currentPdfBlobUrl) {
        alert("Primero debes generar una vista previa.");
        return;
    }
    const now = new Date();
    const filename = `Reporte_CentralNorte_${now.toISOString().split('T')[0]}.pdf`;
    const link = document.createElement('a');
    link.href = currentPdfBlobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// --- LÓGICA PRINCIPAL ---

async function applyFilters() {
    try {
        showLoading(true);

        const startIso = `${document.getElementById('date-start').value}T${document.getElementById('time-start').value}`;
        const endIso = `${document.getElementById('date-end').value}T${document.getElementById('time-end').value}`;
        const interval = document.getElementById('interval-select').value;
        const line = document.getElementById('line-select').value;
        const prodId = document.getElementById('product-select').value;
        const shift = document.getElementById('shift-select').value;

        const vizOptions = {
            curveType: document.getElementById('curve-type').value,
            showStops: document.getElementById('show-stops-check').checked,
            displayMode: document.getElementById('display-mode').value,
            isAllLines: line === 'ALL'
        };

        // URL construction with injected base
        let apiUrl = `${window.API_URLS.dashboard}?interval=${interval}&start=${startIso}&end=${endIso}`;
        if (line !== 'ALL') apiUrl += `&lines=${line}`;
        if (prodId !== 'ALL') apiUrl += `&product_id=${prodId}`;
        if (shift !== 'all') apiUrl += `&shift=${shift}`;

        const response = await fetch(apiUrl);
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || `Error HTTP: ${response.status}`);
        }
        
        const data = await response.json();

        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('kpi-container').style.display = 'flex';
        document.getElementById('charts-container').style.display = 'block';

        updateLastUpdatedTime(data.meta.start, data.meta.end);
        updateKPIs(data.kpis); 
        
        // --- RENDERIZADO MODULAR Y FILTRADO POR ROL ---
        const userRole = window.CURRENT_USER_ROLE || 'client';

        // 1. Evolución
        if (globalUiSettings['card-evolution'][userRole]) {
            const mainCtx = document.getElementById('productionChart').getContext('2d');
            renderProductionChart(mainCtx, data.charts.main, vizOptions, data.downtime.events);
        }

        // 2. Balance
        if (globalUiSettings['card-balance'][userRole]) {
            const compCtx = document.getElementById('comparisonChart').getContext('2d');
            renderComparisonChart(compCtx, data.charts.comparison);
        }

        // 3. Distribución
        if (globalUiSettings['card-distribution'][userRole]) {
            renderSummaryTable(data.products);
            const pieCtx = document.getElementById('productPieChart').getContext('2d');
            renderProductPieChart(pieCtx, data.products);
        }

        // 4. Paradas Detalladas (Tabla)
        // Regla: Config dice visible Y no estamos viendo todas las líneas
        const configPermits = globalUiSettings['card-downtime'][userRole];
        const shouldShowDowntimeTable = configPermits && !vizOptions.isAllLines;
        
        const downtimeContainer = document.getElementById('card-downtime');
        if (downtimeContainer) {
             downtimeContainer.style.display = shouldShowDowntimeTable ? 'block' : 'none';
             if (shouldShowDowntimeTable) {
                 renderDowntimeTable(data.downtime.events);
             }
        }

        // Aplicar reglas visuales finales (para KPIs de paradas y ocultar contenedores vacíos)
        applyVisibilityRules();

    } catch (error) {
        console.error("Error en Dashboard:", error);
        alert("Error al cargar datos: " + error.message);
    } finally {
        showLoading(false);
    }
}

/**
 * Configura las restricciones lógicas entre los selectores de fecha.
 * - La fecha de fin no puede ser menor a la de inicio.
 * - La fecha de inicio no puede ser mayor a la de fin.
 */
function setupDateConstraints() {
    const startInput = document.getElementById('date-start');
    const endInput = document.getElementById('date-end');

    const syncDates = () => {
        const startVal = startInput.value;
        const endVal = endInput.value;

        // 1. Configurar el mínimo de la fecha fin = fecha inicio seleccionada
        if (startVal) {
            endInput.min = startVal;
            
            // Corrección automática: si la fecha fin actual quedó "atrás", la empujamos
            if (endVal && endVal < startVal) {
                endInput.value = startVal;
            }
        } else {
            endInput.removeAttribute('min');
        }

        // 2. Configurar el máximo de la fecha inicio = fecha fin seleccionada
        if (endVal) {
            startInput.max = endVal;
            
            // Corrección automática: si la fecha inicio actual quedó "adelante", la empujamos
            if (startVal && startVal > endVal) {
                startInput.value = endVal;
            }
        } else {
            startInput.removeAttribute('max');
        }
    };

    // Escuchar cambios en ambos inputs
    startInput.addEventListener('change', syncDates);
    endInput.addEventListener('change', syncDates);

    // Ejecutar validación inicial inmediatamente (para aplicar a los valores por defecto)
    syncDates();
}