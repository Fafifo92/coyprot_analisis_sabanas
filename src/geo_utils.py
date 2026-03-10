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
    # Cluster exclusivo para datos de internet
    cluster_datos = MarkerCluster(name="📡 Datos (Morado)").add_to(mapa)

    for _, row in df_clean.iterrows():
        try:
            lat, lon = row["latitud_n"], row["longitud_w"]
            tipo = str(row.get("tipo_llamada", "desconocido")).lower()
            
            # Lógica para diferenciar Datos vs Llamadas
            if "dato" in tipo:
                # Si es dato, intentamos mostrar la celda o el ID
                cid = str(row.get("cell_identity_decimal", ""))
                celda = str(row.get("nombre_celda", ""))
                
                if cid and cid not in ["nan", "None", ""]: num = f"Celda: {cid}"
                elif celda and celda not in ["nan", "None", ""]: num = f"Antena: {celda}"
                else: num = "Tráfico de Datos"
                
                grp = cluster_datos
                color = "purple"
                icon = "globe"
            elif tipo == "saliente":
                num = str(row.get("receptor", "N/A"))
                grp = cluster_salientes
                color = "green"
                icon = "arrow-up"
            else:
                num = str(row.get("originador", "N/A"))
                grp = cluster_entrantes
                color = "blue"
                icon = "arrow-down"

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
    MOTOR DE RUTAS EXCLUSIVO PARA DATOS (PLOTLY).
    - Sin autoplay.
    - Sin leyenda de caja.
    - Muestra fecha/hora grande en el slider.
    - Tooltip estilo "Card" HTML moderno con etiquetas explícitas.
    """
    logger.info(f"Generando Timeline Plotly (Manual/Datos): {output_path}")
    df_clean = _limpiar_coordenadas(df)
    
    if df_clean.empty or "fecha_hora" not in df_clean.columns:
        logger.warning("Sin datos suficientes para rutas.")
        return

    try:
        # 1. Preparar Datos y Ordenar
        df_clean = df_clean.sort_values(by="fecha_hora")
        
        # --- UNIFICACIÓN DE FORMATO DE TIEMPO ---
        # Usamos el mismo string para el Slider y para el Tooltip para evitar discrepancias
        df_clean["Tiempo_Str"] = df_clean["fecha_hora"].dt.strftime('%Y-%m-%d %H:%M:%S')
        df_clean["Fecha_Str"] = df_clean["fecha_hora"].dt.strftime('%Y-%m-%d')
        df_clean["Hora_Str"] = df_clean["fecha_hora"].dt.strftime('%H:%M:%S')

        # Limpieza de columnas clave para el Tooltip
        # Rellenamos vacíos con cadenas vacías para que no salga "nan" o "null"
        df_clean["clean_cell_id"] = df_clean["cell_identity_decimal"].fillna("").astype(str).replace(["nan", "None", "0", "0.0"], "")
        df_clean["clean_nombre_celda"] = df_clean["nombre_celda"].fillna("").astype(str).replace(["nan", "None"], "")

        # --- LÓGICA DE ETIQUETA PRINCIPAL (Título del Tooltip) ---
        def get_main_label(row):
            nom = row["clean_nombre_celda"]
            cid = row["clean_cell_id"]
            
            # Preferencia: Nombre > ID > "Punto de Datos"
            # AQUÍ AGREGAMOS EL PREFIJO EXPLÍCITO QUE PEDISTE
            if nom and len(nom) > 1:
                return f"Antena: {nom}"
            if cid and len(cid) > 0:
                return f"Celda: {cid}"
            return "Ubicación de Datos"

        df_clean["Main_Label"] = df_clean.apply(get_main_label, axis=1)
        
        # 2. Generar Mapa (Plotly Express)
        fig = px.scatter_mapbox(
            df_clean,
            lat="latitud_n",
            lon="longitud_w",
            # Usamos una constante para el color para que no genere leyenda de grupos
            color_discrete_sequence=["#FF0000"], 
            animation_frame="Tiempo_Str", # Usamos el string formateado
            zoom=12,
            height=900
        )

        # 3. Personalización del Tooltip (Estilo CARD moderno + Icono)
        fig.update_traces(
            marker=dict(size=15, opacity=0.9, color="#d62728"), # Rojo Intenso
            hovertemplate="""
            <div style="
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                background-color: white; 
                padding: 12px; 
                border-radius: 8px; 
                border-left: 5px solid #d62728;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                min-width: 220px;
                color: #333;">
                
                <div style="display: flex; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                    <span style="font-size: 24px; margin-right: 10px;">📡</span>
                    <div>
                        <div style="font-size: 14px; font-weight: bold; color: #d62728; line-height: 1.2;">%{customdata[0]}</div>
                    </div>
                </div>
                
                <div style="font-size: 12px; margin-bottom: 4px;">
                    <span style="color: #666;">🆔 ID:</span> 
                    <b>%{customdata[1]}</b>
                </div>
                
                <div style="font-size: 12px;">
                    <span style="color: #666;">📅 Fecha:</span> 
                    <b>%{customdata[2]}</b>
                </div>
                
                <div style="font-size: 12px; margin-top: 4px;">
                    <span style="color: #666;">🕐 Hora:</span> 
                    <b>%{customdata[3]}</b>
                </div>
                
                <div style="font-size: 12px; margin-top: 4px;">
                    <span style="color: #666;">📍 Latitud:</span> 
                    <b>%{lat:.6f}</b>
                </div>
                
                <div style="font-size: 12px; margin-top: 4px;">
                    <span style="color: #666;">🧭 Longitud:</span> 
                    <b>%{lon:.6f}</b>
                </div>
            </div>
            <extra></extra>
            """,
            # Pasamos los datos limpios al customdata: [0]=Label, [1]=ID, [2]=Fecha, [3]=Hora
            customdata=df_clean[["Main_Label", "clean_cell_id", "Fecha_Str", "Hora_Str"]]
        )

        # 4. Layout: Controles y Estilo
        fig.update_layout(
            mapbox_style="open-street-map", 
            margin={"r":0,"t":40,"l":0,"b":0},
            showlegend=False, # Oculta la caja de leyenda superior izquierda

            title=dict(
                text="<b>📍 Recorrido Histórico (Datos de Internet)</b>",
                y=0.99, x=0.01, xanchor='left', yanchor='top',
                font=dict(size=16, color="#333")
            ),
            
            # --- CONTROLES DE REPRODUCCIÓN (SIN AUTOPLAY) ---
            updatemenus=[dict(
                type="buttons",
                showactive=False,
                x=0.05, y=0.03, # Posición abajo a la izquierda, cerca del slider
                xanchor="right", yanchor="bottom",
                pad=dict(t=0, r=10),
                bgcolor="white",
                bordercolor="#ccc",
                borderwidth=1,
                buttons=[
                    dict(
                        label="▶", # Play
                        method="animate",
                        args=[None, dict(frame=dict(duration=800, redraw=True), fromcurrent=True)]
                    ),
                    dict(
                        label="⏸", # Pausa
                        method="animate",
                        args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))]
                    )
                ]
            )],
            
            # --- SLIDER ESTILIZADO ---
            sliders=[dict(
                active=0, 
                yanchor="bottom", xanchor="center",
                x=0.5, y=0.02,
                len=0.85, # Un poco menos ancho para dejar espacio a los botones
                
                currentvalue=dict(
                    font=dict(size=20, color="#d62728", family="Arial Black"), 
                    prefix="🕒 ", 
                    visible=True, 
                    xanchor="center",
                    offset=25
                ),
                bgcolor="#ffffff", bordercolor="#666", borderwidth=1,
                pad=dict(b=10, t=50)
            )]
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # config={'scrollZoom': True} permite zoom con rueda. displayModeBar=True muestra herramientas.
        fig.write_html(output_path, config={'scrollZoom': True, 'displayModeBar': True, 'responsive': True}) 
        logger.info("✅ Mapa Recorrido (Solo Datos, Manual) generado.")

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
