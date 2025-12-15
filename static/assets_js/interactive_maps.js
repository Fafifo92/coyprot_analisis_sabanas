document.addEventListener("DOMContentLoaded", function () {
    const filterInput = document.getElementById("number-filter");
    const typeFilter = document.getElementById("call-type-filter");
    const mapFrame = document.getElementById("map-frame");

    if (!filterInput || !typeFilter || !mapFrame) {
        console.error("❌ No se encontraron los elementos requeridos del mapa.");
        return;
    }

    filterInput.addEventListener("input", updateMap);
    typeFilter.addEventListener("change", updateMap);

    function extraerNumeroBase(valor) {
        const match = valor.match(/^([\d+]+)(\s+\(.+\))?$/);
        return match ? match[1] : valor.trim();
    }

    function updateMap() {
        const seleccionado = filterInput.value.trim();
        const numero = extraerNumeroBase(seleccionado);
        const tipo = typeFilter.value;

        let baseMapUrl = "../maps/mapa_general.html";
        const params = [];

        if (numero) {
            params.push(`number=${encodeURIComponent(numero)}`);
        }
        if (tipo && tipo !== "all") {
            params.push(`type=${encodeURIComponent(tipo)}`);
        }
        if (params.length > 0) {
            baseMapUrl += "?" + params.join("&");
        }

        mapFrame.src = baseMapUrl;
    }
});