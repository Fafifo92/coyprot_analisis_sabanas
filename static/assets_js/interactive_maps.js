// Variable global para rastrear qué mapa estamos viendo
let currentMapType = 'agrupado'; // Por defecto: Clusters (Agrupado)

document.addEventListener("DOMContentLoaded", function () {
    const filterInput = document.getElementById("number-filter");

    // Configurar el buscador si existe
    if (filterInput) {
        // Implementar "Debounce": Esperar a que el usuario termine de escribir
        let timeout = null;
        
        filterInput.addEventListener("input", () => {
            clearTimeout(timeout);
            // Esperar 1 segundo después de la última tecla antes de recargar el mapa
            timeout = setTimeout(updateMapUrl, 1000); 
        });

        // Permitir búsqueda inmediata al presionar Enter
        filterInput.addEventListener("keypress", (e) => {
            if (e.key === 'Enter') {
                clearTimeout(timeout);
                updateMapUrl();
            }
        });
    }
});

// --- Función Principal: Cambiar Tipo de Mapa ---
// Esta función es llamada por los botones del HTML (onclick="switchMap(...)")
window.switchMap = function(type) {
    currentMapType = type;
    
    // 1. Actualizar visualmente los botones (Highlight del activo)
    // Quitamos la clase 'active' de todos los botones de mapa
    document.querySelectorAll('[id^="btn-map-"]').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Ponemos la clase 'active' al botón presionado
    const activeBtn = document.getElementById(`btn-map-${type}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    // 2. Actualizar la fuente del Iframe
    updateMapUrl();
};

// --- Función Auxiliar: Actualizar el Iframe ---
function updateMapUrl() {
    const iframes = document.querySelectorAll('.map-display-area iframe');
    if (!iframes.length) return;

    const filterInput = document.getElementById("number-filter");
    const busqueda = filterInput ? filterInput.value.trim() : "";

    iframes.forEach(iframe => {
        let currentSrc = new URL(iframe.src);
        
        if (busqueda) {
            const match = busqueda.match(/^([\d+]+)/);
            const numeroLimpio = match ? match[1] : busqueda;
            currentSrc.searchParams.set("filter", numeroLimpio);
        } else {
            currentSrc.searchParams.delete("filter");
        }
        
        iframe.src = currentSrc.toString();
    });
}