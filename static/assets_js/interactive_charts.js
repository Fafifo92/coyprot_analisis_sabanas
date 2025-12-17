// Variables globales
let currentFilter = 'entrante'; 
let callChart = null;

// Función global para los botones HTML
window.setChartFilter = function(type) {
    currentFilter = type;
    
    // Actualizar visualmente los botones
    document.querySelectorAll('.filter-btn-group .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const activeBtn = document.getElementById(`btn-${type}`);
    if (activeBtn) activeBtn.classList.add('active');

    // Actualizar gráfico y cerrar tooltip si estaba abierto
    updateChartData();
    hideTooltip();
};

document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById("call-chart");
    const select = document.getElementById("chart-number-filter");

    if (!canvas || !select) return;

    const ctx = canvas.getContext("2d");

    if (typeof TomSelect !== "undefined") {
        new TomSelect("#chart-number-filter", {
            create: false,
            sortField: { field: "text", direction: "asc" },
            placeholder: "Escribe para filtrar...",
            allowEmptyOption: true
        });
    }

    callChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => {
                const ampm = i < 12 ? 'AM' : 'PM';
                const hora = i % 12 === 0 ? 12 : i % 12;
                return `${hora} ${ampm}`;
            }),
            datasets: [{
                label: 'Llamadas',
                data: new Array(24).fill(0),
                fill: true,
                tension: 0.3,
                borderWidth: 3,
                pointRadius: 6, 
                pointHoverRadius: 9, 
                pointBackgroundColor: '#fff',
                pointBorderWidth: 3,
                pointHitRadius: 15 // Facilita el click
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 600, easing: 'easeOutQuart' },
            interaction: {
                mode: 'nearest',
                intersect: true
            },
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: 'rgba(0,0,0,0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false } // Desactivar nativo
            },
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    // Pasamos el evento nativo para obtener coordenadas exactas del mouse
                    showStickyTooltip(index, e.native);
                } else {
                    hideTooltip();
                }
            },
            onHover: (e, el) => {
                e.native.target.style.cursor = el.length ? 'pointer' : 'default';
            }
        }
    });

    updateChartData();
    select.addEventListener("change", () => {
        updateChartData();
        hideTooltip();
    });
});

// --- TOOLTIP INTERACTIVO FIJO (STICKY) ---
function showStickyTooltip(dataIndex, event) {
    let tooltipEl = document.getElementById('chartjs-tooltip');
    
    if (!tooltipEl) {
        tooltipEl = document.createElement('div');
        tooltipEl.id = 'chartjs-tooltip';
        document.body.appendChild(tooltipEl);
    }

    const callsForHour = getCallsForHour(dataIndex);
    
    // Calcular rango horario
    const horaFin = dataIndex + 1;
    const labelHora = `${dataIndex}:00 - ${horaFin}:00`;

    let innerHtml = `
        <div class="tooltip-header d-flex justify-content-between align-items-center">
            <span><b>${labelHora}</b> (${callsForHour.length} llamadas)</span>
            <button onclick="hideTooltip()" style="background:none;border:none;color:#adb5bd;font-size:18px;cursor:pointer;line-height:1;">&times;</button>
        </div>
        <div class="tooltip-body">
    `;

    if (callsForHour.length > 0) {
        // Limitar a mostrar max 50 para no bloquear el navegador si son demasiadas
        callsForHour.slice(0, 50).forEach(call => {
            const fechaObj = new Date(call.fecha_hora);
            const fechaStr = fechaObj.toISOString().split('T')[0];
            
            // Usamos el dato "numero" que viene del backend
            const nombreDisplay = call.numero || "Desconocido";

            let icon = '';
            if (call.latitud && call.longitud) {
                icon = `<a href="https://www.google.com/maps?q=${call.latitud},${call.longitud}" 
                           target="_blank" class="btn-map-pin" title="Ver en Mapa">📍</a>`;
            } else {
                icon = `<span style="opacity:0.2; cursor:default">📞</span>`;
            }

            innerHtml += `
                <div class="tooltip-row">
                    <div style="flex-grow:1; margin-right:10px;">
                        <div style="font-weight:600; color:#fff; font-size:11px;">${nombreDisplay}</div>
                        <div style="font-size:10px; color:#adb5bd;">${fechaStr}</div>
                    </div>
                    <div>${icon}</div>
                </div>
            `;
        });
        
        if(callsForHour.length > 50){
             innerHtml += `<div class="p-2 text-center text-muted" style="font-size:10px">... y ${callsForHour.length - 50} más</div>`;
        }
    } else {
        innerHtml += '<div class="p-3 text-muted text-center">No hay detalles disponibles.</div>';
    }
    
    innerHtml += '</div>';
    tooltipEl.innerHTML = innerHtml;

    // --- POSICIONAMIENTO EXACTO (MOUSE) ---
    const x = event.pageX;
    const y = event.pageY;

    tooltipEl.style.display = 'block';
    tooltipEl.style.opacity = 1;
    
    // Ajuste inteligente para que no se salga de la pantalla
    // Si el click es muy a la derecha, mostrar tooltip a la izquierda del mouse
    if (x + 280 > window.innerWidth) {
        tooltipEl.style.left = (x - 270) + 'px'; 
    } else {
        tooltipEl.style.left = (x + 15) + 'px'; 
    }
    
    tooltipEl.style.top = (y - 50) + 'px';
}

window.hideTooltip = function() {
    const el = document.getElementById('chartjs-tooltip');
    if (el) {
        el.style.opacity = 0;
        setTimeout(() => { el.style.display = 'none'; }, 200);
    }
}

// --- HELPERS ---
function getCallsForHour(horaIndex) {
    const select = document.getElementById("chart-number-filter");
    const numeroSeleccionado = select.value;
    if (typeof CALL_DATA === "undefined") return [];

    let rawData = [];
    if (numeroSeleccionado && CALL_DATA[numeroSeleccionado]) {
        rawData = CALL_DATA[numeroSeleccionado];
    } else {
        Object.values(CALL_DATA).forEach(arr => rawData.push(...arr));
    }

    return rawData.filter(call => {
        const matchFilter = currentFilter === 'todas' || call.tipo_llamada === currentFilter;
        let h = call.hora;
        if (h === undefined && call.fecha_hora) h = new Date(call.fecha_hora).getHours();
        return matchFilter && h === horaIndex;
    });
}

function updateChartData() {
    if (!callChart) return;
    const select = document.getElementById("chart-number-filter");
    const numeroSeleccionado = select.value;
    if (typeof CALL_DATA === "undefined") return;

    let rawData = [];
    if (numeroSeleccionado && CALL_DATA[numeroSeleccionado]) {
        rawData = CALL_DATA[numeroSeleccionado];
    } else {
        Object.values(CALL_DATA).forEach(arr => rawData.push(...arr));
    }

    const horas = new Array(24).fill(0);
    rawData.forEach(call => {
        let h = call.hora;
        if (h === undefined && call.fecha_hora) h = new Date(call.fecha_hora).getHours();
        if (currentFilter === 'todas' || call.tipo_llamada === currentFilter) {
            if (h >= 0 && h < 24) horas[h]++;
        }
    });

    const dataset = callChart.data.datasets[0];
    dataset.data = horas;

    if (currentFilter === 'entrante') {
        dataset.borderColor = '#0d6efd'; 
        dataset.backgroundColor = 'rgba(13, 110, 253, 0.15)';
        dataset.pointBorderColor = '#0d6efd';
    } else if (currentFilter === 'saliente') {
        dataset.borderColor = '#198754'; 
        dataset.backgroundColor = 'rgba(25, 135, 84, 0.15)';
        dataset.pointBorderColor = '#198754';
    } else {
        dataset.borderColor = '#ffc107'; 
        dataset.backgroundColor = 'rgba(255, 193, 7, 0.15)';
        dataset.pointBorderColor = '#ffc107';
    }

    callChart.update();
}