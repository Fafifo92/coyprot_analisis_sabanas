# Analizador de Llamadas Pro v3.0 (Coyprot Analysis)

> **Herramienta avanzada para el analisis forense de registros de detalles de llamadas (CDR), geolocalizacion multinivel y generacion de informes interactivos y PDF profesionales.**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Data-Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Folium](https://img.shields.io/badge/Maps-Folium%20%2B%20Leaflet-77b829?style=for-the-badge&logo=google-maps&logoColor=white)
![ReportLab](https://img.shields.io/badge/PDF-ReportLab-red?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Stable-green?style=for-the-badge)

Este software permite procesar sabanas de llamadas (Excel/CSV), normalizar datos telefonicos colombianos, geolocalizar celdas telefonicas mediante multiples estrategias y generar informes HTML interactivos y PDF profesionales con graficos estadisticos, mapas interactivos y estaticos, tablas detalladas con enlaces a Google Maps, verificacion de integridad SHA-256 y visualizacion de documentos adjuntos categorizados.

---

## Caracteristicas Principales

### Procesamiento de Datos
* **Carga multi-archivo:** Soporte para cargar multiples archivos Excel (.xlsx, .xls) y CSV, cada uno con multiples hojas, acumulando datos de forma incremental.
* **Asistente de mapeo por hojas:** Dialogo con pestanas que permite asignar tipo (Entrantes/Salientes/Datos/Generica/Ignorar) y mapear columnas individualmente por cada hoja del archivo.
* **Auto-deteccion inteligente:** Reconocimiento automatico de tipo de hoja y columnas por coincidencia de palabras clave en nombres de hojas y encabezados.
* **Limpieza automatica:** Normalizacion de numeros telefonicos colombianos (eliminacion de prefijos `57`, `009`, `+57`, espacios) usando la libreria `phonenumbers` de Google.
* **Motor de fechas robusto:** Manejo de fechas seriales de Excel, 6 formatos de texto (Y/m/d, d/m/Y, ISO, compacto) y deteccion automatica como respaldo.
* **Correccion de coordenadas:** Reparacion automatica de coordenadas GPS malformadas (decimales con coma, valores escalados como 6257590 -> 6.257590).
* **Geocodificacion multi-nivel:**
    1. **GPS nativo:** Uso directo de coordenadas latitud/longitud si estan presentes en el archivo.
    2. **Base de datos de celdas:** Cruce vectorizado con `celdas.csv` usando identificadores tecnicos de antena.
    3. **Inferencia por municipio:** Deteccion de patrones de texto (ej: "BARBOSA", "MEDELLIN") en nombres de antena y asignacion de coordenadas del municipio colombiano correspondiente, previa confirmacion del usuario.
* **Geocodificacion inversa:** Identificacion del departamento y municipio mas cercano para cualquier coordenada usando distancia Haversine con optimizacion de bounding-box sobre 1,100+ municipios colombianos.

### Analisis Visual
* **Dashboard interactivo (Chart.js):** Grafico de lineas con distribucion horaria de llamadas (0-23h), filtrable por direccion (Entrantes/Salientes/Todas) y por numero especifico mediante dropdown de busqueda (TomSelect).
* **Tooltips inteligentes:** Inspeccion detallada al hacer clic en puntos del grafico, mostrando hasta 50 llamadas de esa hora con enlaces directos a Google Maps.
* **Graficos de ubicacion:** Visualizacion cruzada de los Top-10 numeros mas frecuentes con su ubicacion geografica mas comun (extraccion de municipio desde nombres de antena).
* **Graficos de frecuencia:** Top-10 numeros mas frecuentes por llamadas recibidas y realizadas con etiquetas de alias.
* **Distribucion horaria:** Grafico de linea mostrando patrones de actividad a lo largo del dia.
* **Tablas interactivas (DataTables):** Tablas con ordenamiento, busqueda, paginacion, agrupacion por numero, filtros por rango de fecha, filtros cascada departamento/municipio y enlaces a Google Maps.

### Mapeo Avanzado
Generacion automatica de 4 tipos de mapas:

1. **Mapa de Clusters (Folium):** Marcadores agrupados con codificacion de color (azul=entrantes, verde=salientes, morado=datos), iconos Font Awesome, popups detallados y control de capas por tipo.
2. **Mapa de Calor (Folium):** Visualizacion de densidad de actividad con radio y difusion configurables.
3. **Mapa de Rutas (Leaflet puro):** Pagina HTML autocontenida con:
   - Navegacion dia por dia (anterior/siguiente/selector)
   - Filtro de rango horario (sliders 0-23h)
   - Marcadores numerados con clustering y spiderfying
   - Linea de ruta cronologica con toggle
   - Barra de resumen con estadisticas
4. **Mapas estaticos PNG (Plotly + Kaleido):** Para insercion en PDF:
   - Mapa de ubicaciones con marcadores por tipo de llamada
   - Mapas de ruta diarios o consolidados con geocodificacion inversa via Nominatim

### Generacion de Informes PDF
* **PDF profesional (ReportLab):** Informe forense con:
  - Portada corporativa con logo, datos del caso y nota de integridad SHA-256
  - Pagina de resumen con tarjetas KPI (total, entrantes, salientes, unicos, promedio) y rankings Top-N
  - Seccion de graficos con 5 imagenes PNG embebidas
  - Tablas detalladas de llamadas agrupadas por numero con departamento, municipio y coordenadas como enlaces clicables a Google Maps
  - Seccion de mapas con mapa de ubicaciones y mapas de ruta (diarios o consolidado)
  - Seccion de notas con enlace FTP, tabla de adjuntos y nota de verificacion
  - Encabezado/pie de pagina en todas las paginas con logo y numeracion
* **Integridad SHA-256:** Generacion de archivo `.sha256` compatible con `sha256sum -c` para verificacion forense de cadena de custodia.

### Gestion Documental
* Carga de multiples adjuntos PDF categorizados (Financiero, Propiedades, Vehiculos, Judicial, Antecedentes, Otros).
* Visualizador integrado en pestanas del informe HTML.
* Tabla de adjuntos en el informe PDF con categorias.

### Sistema de Alias
* Asignacion de nombres legibles a numeros telefonicos (ej: "3001234567" -> "Juan Garcia").
* Propagacion automatica a todos los graficos, tablas, mapas y el informe PDF.

### Exportacion y Distribucion
* Generacion de reporte **HTML local** portable con todos los recursos (JS/CSS/mapas/graficos).
* Generacion de **PDF profesional** con mapas estaticos y tablas detalladas.
* **Subida FTP con TLS** (cifrado) de directorios completos o archivos individuales, con generacion de enlace web compartible.

---

## Requisitos del Sistema

* **Sistema Operativo:** Windows 10/11, macOS o Linux.
* **Python:** Version 3.9 o superior.

### Dependencias Python

Las dependencias se encuentran en `requirements.txt`:

| Paquete | Version | Proposito |
|---|---|---|
| `pandas` | >= 2.0.0 | Procesamiento de datos, lectura Excel/CSV |
| `numpy` | >= 1.24.0 | Operaciones numericas, correccion de coordenadas |
| `jinja2` | >= 3.1.0 | Renderizado de plantillas HTML |
| `folium` | >= 0.15.0 | Mapas interactivos (clusters, calor) |
| `matplotlib` | >= 3.7.0 | Generacion de graficos estaticos PNG |
| `seaborn` | >= 0.13.0 | Estilos mejorados para graficos |
| `phonenumbers` | >= 8.13.0 | Normalizacion de numeros telefonicos (libphonenumber de Google) |
| `openpyxl` | >= 3.1.0 | Lectura de archivos .xlsx |
| `ttkthemes` | >= 3.2.2 | Temas visuales para Tkinter (tema "adapta") |
| `plotly` | >= 5.18.0 | Mapas estaticos PNG para insercion en PDF |
| `python-dotenv` | >= 1.0.0 | Carga de variables de entorno |
| `reportlab` | >= 4.1.0 | Generacion de PDF profesional (motor Platypus) |
| `kaleido` | >= 0.2.1 | Motor de exportacion de imagenes Plotly |

### Librerias Frontend (CDN, incluidas en el informe HTML)

| Libreria | Version | Proposito |
|---|---|---|
| Bootstrap | 5.3.0 | Framework CSS, layout responsivo, pestanas |
| Bootstrap Icons | 1.10.5 | Iconos |
| jQuery | 3.6.0 | Manipulacion DOM |
| DataTables | 1.11.5 | Tablas interactivas con filtros y paginacion |
| Chart.js | latest | Graficos de lineas interactivos |
| TomSelect | 2.2.2 | Dropdowns de busqueda avanzada |
| Leaflet | 1.9.4 | Mapas interactivos (mapa de rutas) |
| Leaflet MarkerCluster | 1.5.3 | Agrupacion de marcadores |

---

## Instalacion y Configuracion

1. **Clonar el repositorio:**
    ```bash
    git clone https://github.com/Fafifo92/coyprot_analisis_sabanas.git
    cd coyprot_analisis_sabanas
    ```

2. **Crear un entorno virtual (Recomendado):**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Configurar variables de entorno (Opcional):**
    Copia `.env.example` a `.env` y configura las variables necesarias:
    ```bash
    cp .env.example .env
    ```

    | Variable | Descripcion | Valor por defecto |
    |---|---|---|
    | `FTP_HOST` | Servidor FTP para subida de informes | *(vacio)* |
    | `FTP_USER` | Usuario FTP | *(vacio)* |
    | `FTP_PASS` | Contrasena FTP | *(vacio)* |
    | `FTP_PUBLIC_HTML` | Directorio remoto base | `public_html` |
    | `LOG_LEVEL` | Nivel de logging (DEBUG, INFO, WARNING, ERROR) | `DEBUG` |
    | `GEO_PROXIMITY_KM` | Radio de proximidad para geocodificacion (km) | *(configurable)* |

5. **Configurar base de datos de celdas (Opcional):**
    Coloca tu archivo maestro de antenas en `static/db/celdas.csv` con columnas para nombre BTS, latitud y longitud.

    > Si no tienes este archivo, el sistema ofrecera inferir la ubicacion por nombres de municipio presentes en los nombres de antena.

---

## Ejecucion

### Interfaz Grafica (GUI) - Recomendado

```bash
python run.py
```

### Puntos de entrada alternativos

```bash
python src/gui.py     # Lanzador GUI legacy
python src/main.py    # Punto de entrada CLI legacy
```

---

## Guia de Uso

### 1. Cargar Archivos
* Haz clic en **"Agregar Archivo"** y selecciona tu Excel/CSV de llamadas.
* Aparecera el **asistente de mapeo por hojas**, donde puedes:
  - Asignar el tipo de cada hoja (Entrantes, Salientes, Datos, Generica o Ignorar).
  - Mapear las columnas de cada hoja a los campos internos (Originador, Receptor, Fecha/Hora, Duracion, Celda, Latitud, Longitud).
* Los indicadores semaforo muestran el estado de carga (Entrantes/Salientes/Datos).
* Puedes agregar mas archivos para acumular datos de multiples fuentes.

### 2. Analizar Datos
* Haz clic en **"Realizar Analisis"** para ejecutar la geocodificacion.
* El sistema aplicara las estrategias en cascada (celdas DB -> inferencia por municipio).
* Si hay registros sin coordenadas, el sistema preguntara si deseas intentar la inferencia por nombre de municipio.

### 3. Enriquecer Datos (Opcional)
* **Asignar Alias:** Haz clic en "Asignar Nombres/Alias" para poner nombres legibles a numeros clave.
* **Datos del Caso:** Ingresa informacion como Cliente, Ciudad, Telefono, Caso y Periodo.
* **Adjuntos PDF:** Agrega documentos categorizados (Financiero, Judicial, Vehiculos, etc.).

### 4. Generar Informe HTML
* Define el nombre del informe.
* Marca "Incluir Logos" para reporte corporativo con membrete.
* Marca "Subir a FTP" si deseas alojarlo en un servidor remoto.
* Haz clic en **"Generar y Exportar Informe"**.

### 5. Exportar PDF
* Selecciona el modo de mapa de ruta:
  - **Diario:** Un mapa por dia con marcadores numerados y ruta.
  - **Consolidado:** Todos los dias en un solo mapa con colores diferenciados.
* Haz clic en **"Exportar PDF"** para generar el informe forense con integridad SHA-256.

---

## Arquitectura del Proyecto

El proyecto sigue una arquitectura por capas con inyeccion de dependencias:

```text
coyprot_analisis_sabanas/
|
|-- run.py                          # Punto de entrada principal (compatible PyInstaller)
|-- requirements.txt                # Dependencias Python
|-- .env.example                    # Plantilla de variables de entorno
|
|-- src/
|   |-- config/                     # Capa de Configuracion
|   |   |-- settings.py             # Singleton de configuracion (rutas, FTP, metadata)
|   |   |-- constants.py            # Constantes centralizadas (tipos, formatos, estilos)
|   |
|   |-- core/                       # Capa de Dominio
|   |   |-- models/                 # Modelos de datos inmutables (dataclasses)
|   |   |   |-- __init__.py         # RouteMapMode, PdfExportConfig, GeographicInfo,
|   |   |                           # PdfAttachment, CaseMetadata, CallStats,
|   |   |                           # ReportConfig, LoadResult
|   |   |-- exceptions.py           # Jerarquia de excepciones personalizada
|   |   |-- interfaces/             # Interfaces (placeholder para futuras abstracciones)
|   |
|   |-- data/                       # Capa de Acceso a Datos
|   |   |-- loaders/
|   |   |   |-- excel_loader.py     # Carga de Excel/CSV con auto-deteccion y mapeo
|   |   |-- repositories/
|   |       |-- cell_tower_repository.py    # Repositorio de celdas (celdas.csv)
|   |       |-- municipality_repository.py  # Repositorio de municipios colombianos
|   |
|   |-- services/                   # Capa de Logica de Negocio
|   |   |-- data_processing_service.py  # Pipeline de procesamiento (fechas, coordenadas, tipos)
|   |   |-- geocoding_service.py        # Orquestador de geocodificacion multi-estrategia
|   |   |-- phone_service.py            # Normalizacion de numeros telefonicos
|   |   |-- upload_service.py           # Subida FTP con TLS
|   |
|   |-- reports/                    # Capa de Generacion de Informes
|   |   |-- report_generator.py     # Orquestador principal del informe HTML
|   |   |-- integrity.py            # Verificacion SHA-256 forense
|   |   |-- builders/
|   |       |-- chart_builder.py    # Graficos Matplotlib/Seaborn (Top, Horario, Ubicacion)
|   |       |-- map_builder.py      # Mapas interactivos (Cluster, Calor, Rutas)
|   |       |-- pdf_builder.py      # Generador PDF profesional (ReportLab Platypus)
|   |       |-- static_map_builder.py  # Mapas PNG estaticos (Plotly + Kaleido)
|   |
|   |-- ui/                         # Capa de Presentacion
|   |   |-- app.py                  # GUI principal (Tkinter + ttkthemes)
|   |   |-- dialogs/
|   |   |   |-- column_mapper.py    # Dialogo de mapeo de columnas individual
|   |   |   |-- sheet_mapper.py     # Dialogo de mapeo por hojas con pestanas
|   |   |-- widgets/
|   |       |-- __init__.py         # TextWidgetHandler (logging a widget)
|   |
|   |-- *.py                        # Modulos legacy (gui.py, main.py, utils.py, etc.)
|
|-- static/
|   |-- assets_img/                 # Logo e iconos (logo.png, info.png)
|   |-- assets_js/
|   |   |-- interactive_charts.js   # Logica Chart.js interactiva con tooltips
|   |   |-- interactive_maps.js     # Switching de iframes de mapas con filtro
|   |-- db/
|       |-- municipios_colombia.csv # Base de datos de 1,100+ municipios colombianos
|       |-- celdas.csv              # Base de datos de celdas (opcional, no incluida)
|
|-- templates/
|   |-- report_template.html        # Plantilla Jinja2 del informe HTML
|                                   # (Bootstrap 5, DataTables, Chart.js, Leaflet)
|
|-- output/                         # Informes generados (gitignored)
|   |-- <nombre_informe>/
|       |-- data/                   # call_data.js + adjuntos PDF
|       |-- graphics/               # 5 graficos PNG
|       |-- maps/                   # 3 mapas HTML interactivos
|       |-- reports/                # HTML + PDF + .sha256
|       |-- static/                 # JS e imagenes copiados
|       |-- static_maps/            # Mapas PNG para PDF
|
|-- logs/                           # Registros (app.log, gitignored)
```

---

## Flujo de Datos

```text
Excel/CSV
    |
    v
ExcelLoader (carga hojas crudas)
    |
    v
SheetColumnMapperDialog (usuario asigna tipos y mapea columnas)
    |
    v
DataProcessingService.process_sheets()
    |-- Mapeo de columnas
    |-- Normalizacion de numeros (PhoneService + phonenumbers)
    |-- Parsing de fechas (serial Excel, 6 formatos texto)
    |-- Correccion de coordenadas GPS
    |-- Normalizacion de tipos de llamada
    v
DataFrame acumulado (soporte multi-archivo)
    |
    v
GeocodingService (estrategias en cascada)
    |-- CellTowerRepository.bulk_lookup (merge vectorizado)
    |-- MunicipalityRepository.find_by_name (inferencia por nombre)
    v
DataFrame enriquecido
    |
    +-- ReportGenerator.generate() --> Informe HTML
    |       |-- ClusterMapBuilder     --> mapa_agrupado.html
    |       |-- HeatMapBuilder        --> mapa_calor.html
    |       |-- RouteMapBuilder       --> mapa_rutas.html
    |       |-- TopCallsChartBuilder  --> graficos PNG
    |       |-- HourlyChartBuilder    --> grafico PNG
    |       |-- TopLocationChartBuilder --> graficos PNG
    |       |-- Jinja2 template       --> informe_llamadas.html
    |
    +-- PdfReportBuilder.build() --> Informe PDF
    |       |-- StaticLocationMapBuilder --> mapa_ubicaciones.png
    |       |-- StaticRouteMapBuilder    --> ruta_*.png
    |       |-- ReportLab Platypus       --> informe_llamadas.pdf
    |       |-- write_sha256_companion   --> informe_llamadas.pdf.sha256
    |
    +-- UploadService.upload() --> Servidor FTP (opcional)
```

---

## Compatibilidad con PyInstaller

La aplicacion es compatible con empaquetado como ejecutable standalone:
- `run.py` resuelve rutas usando `sys._MEIPASS` cuando se ejecuta desde un bundle PyInstaller.
- `settings.py` detecta automaticamente si esta corriendo empaquetado y ajusta las rutas base.

---

## Autor

Desarrollado para **Coyprot** por Fr.
*Analisis de seguridad e inteligencia.*
