# 📊 Analizador de Llamadas Pro (Coyprot Analysis)

> **Herramienta avanzada para el análisis forense de registros de detalles de llamadas (CDR), geolocalización multinivel y generación de informes interactivos.**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Data-Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Folium](https://img.shields.io/badge/Maps-Folium-77b829?style=for-the-badge&logo=google-maps&logoColor=white)
![Status](https://img.shields.io/badge/Status-Stable-green?style=for-the-badge)

Este software permite procesar sábanas de llamadas (Excel/CSV), normalizar datos telefónicos, geolocalizar celdas telefónicas y generar un informe HTML interactivo completo con gráficos estadísticos, mapas de calor, rutas cronológicas y visualización de múltiples documentos adjuntos (Financieros, Antecedentes, Propiedades, etc.).

---

## 🚀 Características Principales

### 🔍 Procesamiento de Datos
* **Mapeo Inteligente:** Asistente gráfico para relacionar columnas de cualquier formato de Excel con el sistema (Origen, Destino, Duración, etc.).
* **Limpieza Automática:** Normalización estricta de números telefónicos (eliminación de prefijos `57`, `009`, espacios, etc.) para evitar duplicados en el análisis.
* **Geocodificación Multi-Nivel (Plan A, B y C):**
    1.  **GPS Nativo:** Uso automático de coordenadas latitud/longitud si están presentes en el archivo.
    2.  **Base de Datos de Celdas:** Cruce automático con `celdas.csv` si existen nombres técnicos de antena (ej: `ANT.BARBOSA-2_R1`).
    3.  **Inferencia por Municipio (Nuevo):** Si los anteriores fallan, el sistema detecta patrones de texto (ej: "BARBOSA", "MEDELLIN") en la celda y asigna coordenadas geográficas del municipio automáticamente tras confirmación del usuario.

### 📈 Análisis Visual
* **Dashboard Interactivo:** Gráficos de líneas con animación suave para analizar tendencias horarias (Entrantes vs Salientes vs Todas).
* **Gráficos de Ubicación (Nuevo):** Visualización de barras que cruza los números más frecuentes con su ubicación geográfica (¿Desde dónde llaman? / ¿Dónde estaba el objetivo?).
* **Tooltips Inteligentes:** Inspección detallada de llamadas al hacer clic en los puntos del gráfico, con enlaces directos a Google Maps.
* **Top 10:** Tablas de frecuencia para identificar rápidamente los números más contactados y los originadores más frecuentes.

### 🗺️ Mapeo Avanzado
Generación automática de 3 tipos de mapas interactivos integrados en una interfaz de pestañas (incluso usando ubicaciones inferidas):
1.  **Mapa Agrupado (Clusters):** Agrupación de marcadores para visualizar grandes volúmenes de datos sin saturación.
2.  **Rutas Cronológicas:** Trazado de líneas secuenciales con marcadores numerados (1, 2, 3...) para seguir el desplazamiento del objetivo.
3.  **Mapa de Calor:** Visualización de densidad para identificar zonas de alta actividad.

### 📎 Gestión Documental Multi-PDF
* Soporte para cargar múltiples adjuntos PDF.
* Categorización automática (Financiero, Vehículos, Judicial, etc.).
* Visualizador integrado dentro de las pestañas del informe HTML final.

### 📤 Exportación
* Generación de reporte **HTML local** (portable, con todos los recursos JS/CSS incluidos).
* Opción de **Subida FTP** automática con generación de enlace web compartible.

---

## 🛠️ Requisitos del Sistema

* **Sistema Operativo:** Windows 10/11, macOS o Linux.
* **Python:** Versión 3.9 o superior.

### Librerías Python
Las dependencias necesarias se encuentran en `requirements.txt`:

```text
pandas
numpy
jinja2
folium
matplotlib
seaborn
phonenumbers
openpyxl
ttkthemes
```

---

## 📦 Instalación y Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone [https://github.com/tu-usuario/coyprot_analisis_sabanas.git](https://github.com/tu-usuario/coyprot_analisis_sabanas.git)
    cd coyprot_analisis_sabanas
    ```

2.  **Crear un entorno virtual (Recomendado):**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar Base de Datos de Celdas (Opcional):**
    Para que la geolocalización por nombre técnico de celda funcione (cuando no hay GPS), debes colocar tu archivo maestro de antenas en:
    `static/db/celdas.csv`
    
    > **Nota:** Si no tienes este archivo, el sistema te ofrecerá la opción de inferir la ubicación por el nombre del municipio presente en la sábana.

---

## ▶️ Ejecución

### Interfaz Gráfica (GUI) - Recomendado
Para iniciar la aplicación con ventanas visuales:

```bash
python src/gui.py
```

### Línea de Comandos (CLI)
Para ejecuciones automatizadas o scripts:

```bash
python src/main.py
```

---

## 📖 Guía de Uso Rápida

1.  **Cargar Sábana:**
    * Haz clic en "Seleccionar Archivo" y elige tu Excel/CSV de llamadas.
    * Si las columnas no son estándar, aparecerá un asistente para mapearlas.
    * **Asistente de Ubicación:** Si faltan coordenadas, el sistema preguntará si deseas intentar inferir la ubicación basándose en los nombres de los municipios (ej: `ANT.BARBOSA`).

2.  **Gestión de Adjuntos:**
    * Usa el botón "➕ Agregar" en la sección de adjuntos.
    * Selecciona tus PDFs (Financiero, Antecedentes, etc.) y asígnales una categoría.

3.  **Enriquecer Datos (Opcional):**
    * **Asignar Nombres:** Haz clic en "👤 Asignar Nombres" para poner alias a los números clave. Esto actualizará todos los gráficos y tablas.
    * **Datos del Caso:** Ingresa información como Cliente, Radicado, Ciudad, etc.

4.  **Generar Informe:**
    * Define el nombre de la carpeta de salida.
    * Marca "Incluir Logos" para un reporte corporativo.
    * Marca "Subir a FTP" si deseas alojarlo en la nube inmediatamente.
    * Haz clic en **"💾 Generar y Exportar Informe"**.

---

## 📂 Estructura del Proyecto

```text
coyprot_analisis_sabanas/
│
├── output/                  # Aquí se guardan los informes generados
├── logs/                    # Registros de ejecución (app.log)
├── src/                     # Código fuente
│   ├── gui.py               # Interfaz Gráfica Principal (Tkinter)
│   ├── main.py              # Punto de entrada CLI
│   ├── excel_utils.py       # Lectura y limpieza de Excel
│   ├── phone_utils.py       # Normalización de números telefónicos
│   ├── geo_utils.py         # Generación de mapas Folium (Clusters, Rutas, Calor)
│   ├── graphics_utils.py    # Generación de gráficos estáticos (Matplotlib)
│   ├── report_generator.py  # Orquestador del reporte HTML (Jinja2)
│   ├── ftp_utils.py         # Cliente FTP
│   ├── cell_geocoder.py     # Lógica de búsqueda de antenas (DB)
│   ├── colombia_data.py     # Lógica de inferencia por Municipios (Nuevo)
│   ├── column_mapper.py     # UI para mapeo de columnas
│   └── utils.py             # Utilidades generales y logging
│
├── static/                  # Recursos estáticos base
│   ├── assets_img/          # Logos e iconos (logo.png, info.png)
│   ├── assets_js/           # Scripts JS para el reporte (Charts, Maps logic)
│   └── db/                  # Base de datos de celdas (celdas.csv)
│
├── templates/               # Plantillas HTML (Jinja2)
│   └── report_template.html
│
└── requirements.txt         # Dependencias
```

---

## 👤 Autor

Desarrollado para **Coyprot** por Fr.
*Análisis de seguridad e inteligencia.*
