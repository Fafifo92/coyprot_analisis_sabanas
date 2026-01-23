import os
import folium
from folium.plugins import HeatMap, MarkerCluster
import pandas as pd
import logging
import plotly.express as px
import plotly.graph_objects as go

# Configurar logger localmente
logger = logging.getLogger(__name__)

# --- CSS FIX PARA MAPAS FOLIUM ---
CSS_LAYER_CONTROL_FIX = """
<style>
    .leaflet-control-layers-list {
        max-height: 400px !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        padding-right: 10px !important;
    }
</style>
"""

def _limpiar_coordenadas(df):
    """Limpieza y validación de coordenadas."""
    if df is None or df.empty:
        return pd.DataFrame()
    
    required = ["latitud_n", "longitud_w"]
    if not all(col in df.columns for col in required):
        return pd.DataFrame()

    df_clean = df.dropna(subset=required).copy()
    # Forzar conversión a numérico
    df_clean["latitud_n"] = pd.to_numeric(df_clean["latitud_n"], errors='coerce')
    df_clean["longitud_w"] = pd.to_numeric(df_clean["longitud_w"], errors='coerce')
    df_clean.dropna(subset=required, inplace=True)

    # Filtrar coordenadas lógicas (Colombia/Mundo)
    df_clean = df_clean[
        (df_clean["latitud_n"] >= -90) & (df_clean["latitud_n"] <= 90) &
        (df_clean["longitud_w"] >= -180) & (df_clean["longitud_w"] <= 180)
    ]
    return df_clean

def generar_mapa_agrupado(df, output_path, nombres_asignados=None):
    """Mapa de Clusters (Folium)."""
    logger.info(f"Generando mapa agrupado: {output_path}")
    df_clean = _limpiar_coordenadas(df)
    if df_clean.empty: return

    center = [df_clean["latitud_n"].mean(), df_clean["longitud_w"].mean()]
    mapa = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
    mapa.get_root().html.add_child(folium.Element(CSS_LAYER_CONTROL_FIX))

    cluster_entrantes = MarkerCluster(name="📥 Entrantes (Azul)").add_to(mapa)
    cluster_salientes = MarkerCluster(name="📤 Salientes (Verde)").add_to(mapa)
    # Cluster nuevo para Datos
    cluster_datos = MarkerCluster(name="📡 Datos (Morado)").add_to(mapa)

    for _, row in df_clean.iterrows():
        try:
            lat, lon = row["latitud_n"], row["longitud_w"]
            tipo = str(row.get("tipo_llamada", "desconocido")).lower()
            
            if "dato" in tipo:
                # Si es dato, mostramos la celda o el ID
                cid = str(row.get("cell_identity_decimal", ""))
                celda = str(row.get("nombre_celda", ""))
                # Priorizar ID, si no Nombre, si no "Datos"
                if cid and cid != "nan": num = cid
                elif celda and celda != "nan": num = celda
                else: num = "Tráfico de Datos"
                
                grp = cluster_datos; color = "purple"; icon = "globe"
            elif tipo == "saliente":
                num = str(row.get("receptor", "N/A"))
                grp = cluster_salientes; color = "green"; icon = "arrow-up"
            else:
                num = str(row.get("originador", "N/A"))
                grp = cluster_entrantes; color = "blue"; icon = "arrow-down"

            alias = nombres_asignados.get(str(row.get("originador", "")), "") if nombres_asignados else ""
            label = f"{num} ({alias})" if alias else num
            
            popup = f"<b>{label}</b><br>{row['fecha_hora']}<br>{tipo}"
            folium.Marker([lat, lon], popup=popup, icon=folium.Icon(color=color, icon=icon, prefix="fa")).add_to(grp)
        except: continue

    folium.LayerControl().add_to(mapa)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mapa.save(output_path)

def generar_mapa_rutas(df, output_path, nombres_asignados=None):
    """
    NUEVO MOTOR DE RUTAS (PLOTLY) - MANUAL Y ESTILIZADO.
    - Soporte para hoja de DATOS (Muestra cell_identity o nombre celda).
    - Sin botones Play/Pausa (Control manual puro).
    - Slider resaltado en "caja" visible.
    - Sin líneas, solo puntos rojos.
    """
    logger.info(f"Generando Timeline Plotly (Manual): {output_path}")
    df_clean = _limpiar_coordenadas(df)
    
    if df_clean.empty or "fecha_hora" not in df_clean.columns:
        logger.warning("Sin datos suficientes para rutas.")
        return

    try:
        # 1. Preparar Datos
        df_clean = df_clean.sort_values(by="fecha_hora")
        df_clean["Tiempo"] = df_clean["fecha_hora"].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Función de etiqueta inteligente mejorada para DATOS
        def get_label(row):
            tipo = str(row.get("tipo_llamada", "")).lower()
            
            # Si es un registro de DATOS
            if "dato" in tipo:
                # Prioridad 1: Cell Identity Decimal
                cid = row.get("cell_identity_decimal")
                if pd.notna(cid) and str(cid).strip() not in ["", "nan", "None"]:
                    return f"Celda ID: {cid}"
                
                # Prioridad 2: Nombre Celda
                nom = row.get("nombre_celda")
                if pd.notna(nom) and str(nom).strip() not in ["", "nan", "None"]:
                    return f"Antena: {nom}"
                
                return "Datos (Ubicación)"

            # Lógica normal para llamadas
            num = str(row.get("receptor") if tipo == "saliente" else row.get("originador"))
            alias = nombres_asignados.get(num, "") if nombres_asignados else ""
            return f"{num} ({alias})" if alias else num

        df_clean["Objetivo"] = df_clean.apply(get_label, axis=1)
        
        # 2. Generar Mapa (Plotly Express)
        
        # Configurar tooltip dinámico
        hover_cols = {
            "latitud_n": False, 
            "longitud_w": False, 
            "tipo_llamada": True, 
            "duracion": True, 
            "nombre_celda": True, 
            "Tiempo": True
        }
        # Si existe la columna de ID de celda, la agregamos al tooltip
        if "cell_identity_decimal" in df_clean.columns:
            hover_cols["cell_identity_decimal"] = True
            
        fig = px.scatter_mapbox(
            df_clean,
            lat="latitud_n",
            lon="longitud_w",
            color="Objetivo", 
            animation_frame="Tiempo",
            hover_name="Objetivo",
            hover_data=hover_cols,
            zoom=12,
            height=900,
            color_discrete_sequence=["#FF0000"] * len(df_clean["Objetivo"].unique())
        )

        # 3. Estilos de Puntos (Rojos, sin líneas)
        fig.update_traces(marker=dict(size=10, opacity=0.9))

        # 4. Layout Limpio
        fig.update_layout(
            mapbox_style="open-street-map", 
            margin={"r":0,"t":50,"l":0,"b":0},
            
            title=dict(
                text="<b>Análisis de Recorrido por Datos</b>",
                y=0.98, x=0.01, xanchor='left', yanchor='top'
            ),
            
            legend=dict(
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor="#333", borderwidth=1,
                yanchor="top", y=0.95, xanchor="left", x=0.01,
                title_text="Objetivos / Celdas"
            ),
            
            # Sin updatemenus (Botones eliminados)
            
            # SLIDER ESTILIZADO (CAJA VISIBLE)
            sliders=[dict(
                active=0, 
                yanchor="bottom", xanchor="center",
                x=0.5, y=0.02,  # Centrado abajo
                len=0.9,        # Ocupa casi todo el ancho
                
                currentvalue=dict(
                    font=dict(size=22, color="red", family="Arial Black"), 
                    prefix="📅 ", 
                    visible=True, 
                    xanchor="center", # Fecha centrada sobre la barra
                    offset=25
                ),
                
                # Estilo de la "Caja" del slider
                bgcolor="#f8f9fa",      # Fondo gris claro
                bordercolor="#333",     # Borde oscuro
                borderwidth=2,          # Grosor del borde
                pad=dict(b=10, t=50, l=20, r=20), # Margen interno generoso
                
                # Ocultar ticks labels de abajo (manchón negro)
                font=dict(size=1, color="rgba(0,0,0,0)") 
            )]
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Scroll Zoom activado
        fig.write_html(output_path, config={'scrollZoom': True, 'displayModeBar': True}) 
        logger.info("✅ Mapa Recorrido (Manual Estilizado) generado.")

    except Exception as e:
        logger.error(f"❌ Error generando mapa Plotly: {e}")

def generar_mapa_calor(df, output_path):
    """Mapa de Calor (Folium) - Fondo Claro."""
    logger.info(f"Generando mapa de calor: {output_path}")
    df_clean = _limpiar_coordenadas(df)
    if df_clean.empty: return
    center = [df_clean["latitud_n"].mean(), df_clean["longitud_w"].mean()]
    
    mapa = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
    
    heat_data = [[row["latitud_n"], row["longitud_w"]] for _, row in df_clean.iterrows()]
    HeatMap(heat_data, radius=15, blur=20).add_to(mapa)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mapa.save(output_path)