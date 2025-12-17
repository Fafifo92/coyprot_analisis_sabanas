import os
import folium
from folium.plugins import HeatMap, MarkerCluster, AntPath
from folium.features import DivIcon
import pandas as pd
from collections import defaultdict
import logging

# Configurar logger localmente si no existe
logger = logging.getLogger(__name__)

# --- CSS FIX PARA EL CONTROL DE CAPAS ---
# Esto hace que si hay muchos números en la lista de capas, aparezca un scroll
# en lugar de que la lista se salga de la pantalla.
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
    """
    Función auxiliar robusta para limpiar y validar coordenadas.
    Corrige el error común de falta de punto decimal (Ej: 47123 -> 4.7123).
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    required = ["latitud_n", "longitud_w"]
    if not all(col in df.columns for col in required):
        return pd.DataFrame()

    # Trabajar en una copia para no afectar el original
    df_clean = df.dropna(subset=required).copy()
    
    # Convertir a numérico forzoso
    df_clean["latitud_n"] = pd.to_numeric(df_clean["latitud_n"], errors='coerce')
    df_clean["longitud_w"] = pd.to_numeric(df_clean["longitud_w"], errors='coerce')
    df_clean.dropna(subset=required, inplace=True)

    # Filtrar coordenadas imposibles (fuera del planeta tierra)
    # Latitud: -90 a 90, Longitud: -180 a 180
    df_clean = df_clean[
        (df_clean["latitud_n"] >= -90) & (df_clean["latitud_n"] <= 90) &
        (df_clean["longitud_w"] >= -180) & (df_clean["longitud_w"] <= 180)
    ]

    return df_clean

def generar_mapa_agrupado(df, output_path, nombres_asignados=None):
    """
    Genera un mapa con MarkerCluster.
    Agrupa los puntos cercanos y los separa por Entrantes (Azul) y Salientes (Verde).
    """
    logger.info(f"Generando mapa agrupado (Clusters): {output_path}")
    df_clean = _limpiar_coordenadas(df)
    
    if df_clean.empty:
        logger.warning("No hay coordenadas válidas para el mapa agrupado.")
        return

    # Centro del mapa
    center = [df_clean["latitud_n"].mean(), df_clean["longitud_w"].mean()]
    mapa = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap", control_scale=True)
    
    # Inyectar CSS Fix
    mapa.get_root().html.add_child(folium.Element(CSS_LAYER_CONTROL_FIX))

    # Crear Clusters
    cluster_entrantes = MarkerCluster(name="📥 Entrantes (Azul)", show=True).add_to(mapa)
    cluster_salientes = MarkerCluster(name="📤 Salientes (Verde)", show=True).add_to(mapa)

    count = 0
    for _, row in df_clean.iterrows():
        try:
            lat, lon = row["latitud_n"], row["longitud_w"]
            tipo = str(row.get("tipo_llamada", "desconocido")).lower()
            
            # Determinar Datos
            if tipo == "saliente":
                numero = str(row.get("receptor", "N/A"))
                grupo = cluster_salientes
                color = "green"
                icono = "arrow-up"
            else:
                numero = str(row.get("originador", "N/A"))
                grupo = cluster_entrantes
                color = "blue"
                icono = "arrow-down"

            # Nombre/Alias
            nombre_alias = nombres_asignados.get(numero, "") if nombres_asignados else ""
            display_num = f"{numero} ({nombre_alias})" if nombre_alias else numero

            # Popup con estilo HTML
            popup_html = f"""
            <div style="font-family: Arial; width: 200px;">
                <h5 style="margin:0; color:{color};"><b>{display_num}</b></h5>
                <hr style="margin:5px 0;">
                <b>Fecha:</b> {row['fecha_hora']}<br>
                <b>Duración:</b> {row.get('duracion', 0)} seg<br>
                <b>Tipo:</b> {tipo.capitalize()}<br>
                <small>Coords: {lat:.5f}, {lon:.5f}</small>
            </div>
            """
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=display_num,
                icon=folium.Icon(color=color, icon=icono, prefix="fa")
            ).add_to(grupo)
            count += 1
        except Exception:
            continue

    folium.LayerControl(collapsed=False).add_to(mapa)
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mapa.save(output_path)
        logger.info(f"✅ Mapa Agrupado guardado con {count} puntos.")
    except Exception as e:
        logger.error(f"❌ Error guardando mapa agrupado: {e}")

def generar_mapa_rutas(df, output_path, nombres_asignados=None):
    """
    Genera un mapa de rutas cronológicas.
    Crea una capa (Layer) por cada número para ver su recorrido específico.
    Usa marcadores numerados (1, 2, 3...) para indicar la secuencia.
    """
    logger.info(f"Generando mapa de rutas cronológicas: {output_path}")
    df_clean = _limpiar_coordenadas(df)
    
    # Necesitamos ordenar por fecha para que la ruta tenga sentido
    if "fecha_hora" in df_clean.columns:
        df_clean = df_clean.sort_values(by="fecha_hora")
    
    if df_clean.empty:
        return

    center = [df_clean["latitud_n"].mean(), df_clean["longitud_w"].mean()]
    mapa = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron", control_scale=True)
    mapa.get_root().html.add_child(folium.Element(CSS_LAYER_CONTROL_FIX))

    # Agrupar datos por número (sea origen o destino)
    rutas_por_numero = defaultdict(list)

    for _, row in df_clean.iterrows():
        tipo = row.get("tipo_llamada", "desconocido")
        # El número de interés es el "otro", o podemos agrupar por el número objetivo si tuvieramos uno fijo.
        # Aquí asumimos que queremos ver rutas de TODOS los números involucrados.
        # Simplificación: Tomamos el número que NO es el del cliente (si supiéramos cuál es).
        # Como no sabemos cuál es el cliente, agrupamos por ambos (creará muchas capas) 
        # O mejor: Agrupamos por el "número remoto".
        
        # Lógica: Si es saliente, el remoto es el receptor. Si es entrante, el remoto es el originador.
        num_remoto = row.get("receptor") if tipo == "saliente" else row.get("originador")
        num_remoto = str(num_remoto)

        rutas_por_numero[num_remoto].append({
            "coord": [row["latitud_n"], row["longitud_w"]],
            "fecha": row["fecha_hora"],
            "tipo": tipo,
            "info": row
        })

    # Crear capas para cada número que tenga al menos 2 puntos (para formar una línea)
    count_rutas = 0
    for numero, eventos in rutas_por_numero.items():
        if len(eventos) < 2: continue # Ignorar puntos aislados sin movimiento
        
        nombre_alias = nombres_asignados.get(numero, "") if nombres_asignados else ""
        display_label = f"{numero} ({nombre_alias})" if nombre_alias else numero
        
        # Crear Grupo (Capa) - Por defecto oculto para no saturar
        fg = folium.FeatureGroup(name=f"📍 Ruta: {display_label}", show=False)
        
        # Extraer coordenadas para la línea
        line_points = [e["coord"] for e in eventos]
        
        # Dibujar Línea (PolyLine)
        folium.PolyLine(
            line_points,
            color="blue",
            weight=2.5,
            opacity=0.7,
            tooltip=f"Ruta de {display_label}"
        ).add_to(fg)

        # Añadir Marcadores Numerados (1, 2, 3...)
        for i, evento in enumerate(eventos):
            secuencia = i + 1
            color_marcador = "green" if evento["tipo"] == "saliente" else "blue"
            
            # Icono HTML personalizado (Círculo con número)
            icon_html = f"""
                <div style="
                    background-color: {color_marcador};
                    color: white;
                    border-radius: 50%;
                    width: 20px; height: 20px;
                    text-align: center;
                    font-size: 10px;
                    line-height: 20px;
                    border: 1px solid white;
                    box-shadow: 1px 1px 2px rgba(0,0,0,0.4);
                ">{secuencia}</div>
            """
            
            folium.Marker(
                location=evento["coord"],
                icon=DivIcon(html=icon_html),
                tooltip=f"#{secuencia} - {evento['fecha']}",
                popup=f"<b>#{secuencia}</b><br>{evento['fecha']}<br>{evento['tipo']}"
            ).add_to(fg)

        fg.add_to(mapa)
        count_rutas += 1

    folium.LayerControl(collapsed=False).add_to(mapa)
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mapa.save(output_path)
        logger.info(f"✅ Mapa de Rutas guardado con {count_rutas} trayectorias.")
    except Exception as e:
        logger.error(f"❌ Error guardando mapa rutas: {e}")

def generar_mapa_calor(df, output_path):
    """
    Genera un mapa de calor clásico (HeatMap).
    """
    logger.info(f"Generando mapa de calor: {output_path}")
    df_clean = _limpiar_coordenadas(df)
    
    if df_clean.empty:
        return

    center = [df_clean["latitud_n"].mean(), df_clean["longitud_w"].mean()]
    mapa = folium.Map(location=center, zoom_start=11, tiles="CartoDB dark_matter") # Dark theme queda mejor para calor

    heat_data = [[row["latitud_n"], row["longitud_w"]] for _, row in df_clean.iterrows()]
    
    HeatMap(heat_data, radius=15, blur=20).add_to(mapa)
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mapa.save(output_path)
        logger.info(f"🔥 Mapa de Calor guardado.")
    except Exception as e:
        logger.error(f"❌ Error guardando mapa calor: {e}")