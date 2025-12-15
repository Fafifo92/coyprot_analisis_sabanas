document.addEventListener("DOMContentLoaded", function () {
    const chartSelect = document.getElementById("chart-number-filter");
    const canvas = document.getElementById("call-chart");

    if (!chartSelect || !canvas) {
        console.error("❌ Elementos requeridos no encontrados en el DOM.");
        return;
    }

    if (typeof TomSelect !== "undefined") {
        new TomSelect("#chart-number-filter", {
            allowEmptyOption: true,
            placeholder: "Buscar número...",
            maxOptions: 100,
            sortField: { field: "text", direction: "asc" }
        });
    }

    const ctx = canvas.getContext("2d");
    let callChart;
    let currentFilter = 'todas';
    let tooltipEl = null;
    let tooltipOpen = false;

    function createFilterButton(type, color, label) {
        const btn = document.createElement("button");
        btn.className = `btn btn-sm fw-bold me-2 btn-outline-${color}`;
        btn.textContent = label;
        btn.dataset.type = type;
        btn.style.borderWidth = "2px";
        btn.addEventListener("click", () => {
            currentFilter = type;
            document.querySelectorAll(".chart-filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            updateChart();
        });
        btn.classList.add("chart-filter-btn");
        return btn;
    }

    const chartContainer = canvas.closest(".chart-container");
    if (chartContainer && !chartContainer.querySelector(".filter-buttons-container")) {
        const buttonGroup = document.createElement("div");
        buttonGroup.className = "d-flex justify-content-center mb-3 mt-2 filter-buttons-container";
        buttonGroup.appendChild(createFilterButton("entrante", "primary", "Entrantes"));
        buttonGroup.appendChild(createFilterButton("todas", "warning", "Todas"));
        buttonGroup.appendChild(createFilterButton("saliente", "success", "Salientes"));
        chartContainer.insertBefore(buttonGroup, canvas);
    }

    function getCallData(numero) {
        if (typeof CALL_DATA === "undefined") return [];
        return numero ? CALL_DATA[numero] || [] : [];
    }

    function crearTooltipSiNoExiste() {
        if (!tooltipEl) {
            tooltipEl = document.createElement("div");
            tooltipEl.id = 'chartjs-tooltip';
            tooltipEl.style.background = 'rgba(0, 0, 0, 0.85)';
            tooltipEl.style.borderRadius = '8px';
            tooltipEl.style.color = 'white';
            tooltipEl.style.maxHeight = '250px';
            tooltipEl.style.overflowY = 'auto';
            tooltipEl.style.pointerEvents = 'auto';
            tooltipEl.style.position = 'absolute';
            tooltipEl.style.transition = 'all .1s ease';
            tooltipEl.style.padding = '10px';
            tooltipEl.style.fontSize = '13px';
            tooltipEl.style.zIndex = 9999;
            tooltipEl.style.display = 'none';
            document.body.appendChild(tooltipEl);
        }
    }

    function mostrarTooltip(dataIndex, evt) {
        const numero = chartSelect.value.trim();
        const llamadas = getCallData(numero).filter(call => {
            const hora = new Date(call.fecha_hora).getHours();
            const tipo = currentFilter === "todas" || call.tipo_llamada === currentFilter;
            return hora === dataIndex && tipo;
        });

        if (llamadas.length === 0) return;

        const hora12 = dataIndex % 12 === 0 ? 12 : dataIndex % 12;
        const ampm = dataIndex < 12 ? "AM" : "PM";
        const horaLabel = `${hora12} ${ampm}`;

        tooltipEl.innerHTML = `
            <b>${horaLabel} — ${llamadas.length} llamada${llamadas.length !== 1 ? 's' : ''}</b><br>
            ${llamadas.map(ll => {
                const fecha = new Date(ll.fecha_hora).toISOString().split("T")[0];
                return `
                    • ${numero} el ${fecha}
                    <a href="https://www.google.com/maps?q=${ll.latitud},${ll.longitud}" 
                       target="_blank" 
                       class="btn btn-sm btn-link text-danger ms-1 p-0"
                       title="Mostrar en Google Maps">📍</a>
                `;
            }).join("<br>")}
        `;

        tooltipEl.style.left = evt.clientX + 10 + 'px';
        tooltipEl.style.top = evt.clientY + 10 + 'px';
        tooltipEl.style.display = 'block';
        tooltipOpen = true;
    }

    function ocultarTooltip() {
        if (tooltipEl) {
            tooltipEl.style.display = 'none';
            tooltipOpen = false;
        }
    }

    function updateChart() {
        const numero = chartSelect.value.trim();
        const data = getCallData(numero);

        const horas = Array.from({ length: 24 }, (_, i) => i);
        const counts = {
            entrante: new Array(24).fill(0),
            saliente: new Array(24).fill(0),
            todas: new Array(24).fill(0)
        };

        data.forEach(call => {
            const hora = new Date(call.fecha_hora).getHours();
            const tipo = call.tipo_llamada;
            if (tipo === 'entrante') counts.entrante[hora]++;
            else if (tipo === 'saliente') counts.saliente[hora]++;
            counts.todas[hora]++;
        });

        if (callChart) callChart.destroy();

        const colores = {
            todas: { borde: 'orange', fondo: 'rgba(255,165,0,0.2)' },
            entrante: { borde: 'blue', fondo: 'rgba(0,0,255,0.2)' },
            saliente: { borde: 'green', fondo: 'rgba(0,128,0,0.2)' }
        };

        const color = colores[currentFilter];

        crearTooltipSiNoExiste();

        callChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: horas.map(h => {
                    const hora12 = h % 12 === 0 ? 12 : h % 12;
                    const ampm = h < 12 ? "AM" : "PM";
                    return `${hora12} ${ampm}`;
                }),
                datasets: [{
                    label: "Llamadas por hora",
                    data: counts[currentFilter],
                    borderColor: color.borde,
                    backgroundColor: color.fondo,
                    fill: true,
                    pointBackgroundColor: color.borde,
                    borderWidth: 2,
                    pointRadius: 6,
                    hitRadius: 12,
                    hoverRadius: 10
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    tooltip: { enabled: false },
                    legend: {
                        display: true,
                        labels: {
                            color: color.borde,
                            font: { size: 16, weight: "bold" },
                            boxWidth: 20,
                            boxHeight: 12
                        },
                        title: {
                            display: true,
                            text: "📈 Leyenda de Datos",
                            color: "black",
                            font: { size: 14, weight: "bold" },
                            padding: 10
                        }
                    }
                },
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        mostrarTooltip(index, evt.native);
                    } else {
                        ocultarTooltip();
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: "Hora del día",
                            color: "black",
                            font: { size: 18, weight: "bold" },
                            padding: { top: 10 }
                        },
                        ticks: {
                            color: "#333",
                            font: { size: 12 }
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: "Número de llamadas",
                            color: "black",
                            font: { size: 18, weight: "bold" },
                            padding: { bottom: 10 }
                        },
                        ticks: {
                            beginAtZero: true,
                            stepSize: 1,
                            precision: 0,
                            color: "#333",
                            font: { size: 12 }
                        }
                    }
                }
            }
        });
    }

    document.addEventListener("click", function (e) {
        if (tooltipOpen && tooltipEl && !tooltipEl.contains(e.target) && !canvas.contains(e.target)) {
            ocultarTooltip();
        }
    });

    chartSelect.addEventListener("change", updateChart);
    updateChart();
});