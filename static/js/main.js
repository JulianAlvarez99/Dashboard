/* static/js/main.js */

import { renderProductionChart, renderComparisonChart, renderProductPieChart } from './modules/charts.js';
import { updateKPIs, renderDowntimeTable, renderSummaryTable, updateLastUpdatedTime, showLoading } from './modules/ui.js';

/**
 * Inicialización de la aplicación.
 */

// Variable global para guardar la URL del PDF generado y poder descargarlo
let currentPdfBlobUrl = null;
let pdfModalInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    loadProducts(); 
    setupEventListeners();
    setInitialDefaults();
    
    // Inicializar instancia del modal de Bootstrap
    const modalEl = document.getElementById('pdfModal');
    if (modalEl) {
        pdfModalInstance = new bootstrap.Modal(modalEl);
    }
});

/**
 * Carga la lista de productos para poblar el filtro select.
 */
async function loadProducts() {
    try {
        const response = await fetch('/api/products_list');
        const products = await response.json();
        const select = document.getElementById('product-select');
        
        // Resetear opción default
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

/**
 * Configura los listeners de los botones y controles.
 */
function setupEventListeners() {
    document.getElementById('btn-filter').addEventListener('click', applyFilters);
    
    // CAMBIO: El botón principal ahora abre la modal
    document.getElementById('btn-pdf').addEventListener('click', openPDFModal);
    
    // Listeners de la modal
    document.getElementById('btn-refresh-preview').addEventListener('click', generatePDFPreview);
    document.getElementById('btn-download-final').addEventListener('click', downloadGeneratedPDF);
    
    // Listener para selectores (actualización automática opcional, mejor manual para rendimiento)
    // document.getElementById('pdf-format').addEventListener('change', generatePDFPreview);
}

/**
 * Establece los valores por defecto en los inputs (Ayer -> Hoy).
 */
function setInitialDefaults() {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);

    // Fechas: Ayer 06:00 a Hoy 06:00
    document.getElementById('date-start').value = yesterday.toISOString().split('T')[0];
    document.getElementById('time-start').value = "06:00";
    
    document.getElementById('date-end').value = now.toISOString().split('T')[0];
    document.getElementById('time-end').value = "06:00";
    
    // Valores por defecto de UI
    document.getElementById('interval-select').value = '1h';
    document.getElementById('line-select').value = 'ALL';
    document.getElementById('product-select').value = 'ALL';
    document.getElementById('curve-type').value = 'stepped'; 
    document.getElementById('show-stops-check').checked = false;
    
    // No llamamos a applyFilters() aquí para iniciar con dashboard vacío
}

/**
 * Genera un PDF de la vista actual del dashboard usando html2pdf.js.
 * Se ejecuta totalmente en el cliente, capturando los gráficos rendered.
 */
function openPDFModal() {
    // Abrir modal
    if (pdfModalInstance) pdfModalInstance.show();
    
    // Generar la vista previa inicial
    generatePDFPreview();
}

function generatePDFPreview() {
    const element = document.getElementById('dashboard-content');
    const iframe = document.getElementById('pdf-preview-frame');
    const spinner = document.getElementById('pdf-loading-spinner');
    
    // Mostrar spinner, ocultar iframe
    spinner.style.display = 'block';
    iframe.style.opacity = '0.3';
    
    // Obtener configuración del usuario
    const format = document.getElementById('pdf-format').value;
    const orientation = document.getElementById('pdf-orientation').value;

    // Configuración html2pdf
    const opt = {
        margin:       [5, 5, 5, 5],
        filename:     'preview.pdf', // Nombre temporal interno
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true, logging: false, allowTaint: true },
        jsPDF:        { unit: 'mm', format: format, orientation: orientation },
        pagebreak:    { mode: ['avoid-all', 'css', 'legacy'] }
    };

    // MODO SEGURO: Ocultar iconos conflictivos
    document.body.classList.add('generating-pdf');

    // Generar Blob para visualización
    html2pdf().set(opt).from(element).output('bloburl')
        .then(function(pdfUrl) {
            // Guardar referencia global
            currentPdfBlobUrl = pdfUrl;
            
            // Mostrar en el iframe
            iframe.src = pdfUrl;
            
            // Restaurar UI
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

    // Nombre del archivo
    const now = new Date();
    const dateStr = now.toISOString().split('T')[0];
    const timeStr = now.toTimeString().split(' ')[0].replace(/:/g, '-');
    const filename = `Reporte_CentralNorte_${dateStr}_${timeStr}.pdf`;

    // Crear enlace de descarga invisible
    const link = document.createElement('a');
    link.href = currentPdfBlobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Opcional: Cerrar modal después de descargar
    // if (pdfModalInstance) pdfModalInstance.hide();
}

/**
 * Recopila filtros, llama a la API y orquesta el renderizado.
 */
async function applyFilters() {
    try {
        showLoading(true);

        // 1. Recopilación de Parámetros del DOM
        const startIso = `${document.getElementById('date-start').value}T${document.getElementById('time-start').value}`;
        const endIso = `${document.getElementById('date-end').value}T${document.getElementById('time-end').value}`;
        const interval = document.getElementById('interval-select').value;
        const line = document.getElementById('line-select').value;
        const prodId = document.getElementById('product-select').value;
        const shift = document.getElementById('shift-select').value;

        // 2. Opciones de Visualización (No van a la API)
        const vizOptions = {
            curveType: document.getElementById('curve-type').value,
            showStops: document.getElementById('show-stops-check').checked,
            displayMode: document.getElementById('display-mode').value,
            isAllLines: line === 'ALL'
        };

        // 3. Construcción de URL para la API
        // Usamos fetch nativo aquí para control total de los parámetros complejos
        let apiUrl = `/api/dashboard?interval=${interval}&start=${startIso}&end=${endIso}`;
        
        if (line !== 'ALL') apiUrl += `&lines=${line}`;
        if (prodId !== 'ALL') apiUrl += `&product_id=${prodId}`;
        if (shift !== 'all') apiUrl += `&shift=${shift}`;

        // 4. Petición de Datos
        const response = await fetch(apiUrl);
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || `Error HTTP: ${response.status}`);
        }
        
        const data = await response.json();

        // 5. Gestión de Estado de la UI (Mostrar contenedores ocultos)
        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('kpi-container').style.display = 'flex';
        document.getElementById('charts-container').style.display = 'block';

        // Si vemos todas las líneas, ocultamos detalle de paradas (es confuso mezclarlas)
        const downtimeElements = document.querySelectorAll('.downtime-card-group, .downtime-list-section');
        downtimeElements.forEach(el => {
            el.style.display = vizOptions.isAllLines ? 'none' : 'block';
        });

        // 6. Renderizado de Componentes
        updateLastUpdatedTime(data.meta.start, data.meta.end);
        updateKPIs(data.kpis); 
        
        if (!vizOptions.isAllLines) {
            renderDowntimeTable(data.downtime.events);
        }
        
        renderSummaryTable(data.products);

        // Renderizar Gráficos
        const mainCtx = document.getElementById('productionChart').getContext('2d');
        renderProductionChart(mainCtx, data.charts.main, vizOptions, data.downtime.events);
        
        const compCtx = document.getElementById('comparisonChart').getContext('2d');
        renderComparisonChart(compCtx, data.charts.comparison);

        const pieCtx = document.getElementById('productPieChart').getContext('2d');
        renderProductPieChart(pieCtx, data.products);

    } catch (error) {
        console.error("Error en Dashboard:", error);
        alert("Error al cargar datos: " + error.message);
    } finally {
        showLoading(false);
    }
}