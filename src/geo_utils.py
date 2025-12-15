import os
import folium
from folium.plugins import HeatMap
import pandas as pd


def generar_mapa_interactivo(df, output_path):
    """
    Genera un mapa interactivo que permite filtrar por número de teléfono y tipo de llamada.
    """
    df_clean = df.dropna(subset=["latitud_n", "longitud_w"])
    if df_clean.empty:
        print("⚠️ No hay datos válidos para generar el mapa.")
        return

    # Crear un mapa centrado en la ubicación media
    map_center = [df_clean["latitud_n"].mean(), df_clean["longitud_w"].mean()]
    mapa = folium.Map(location=map_center, zoom_start=10)

    # Crear un diccionario de grupos de números
    markers_group = {}

    for _, row in df_clean.iterrows():
        numero = row["receptor"] if row["tipo_llamada"] == "saliente" else row["originador"]
        tipo = row["tipo_llamada"].capitalize()
        info_popup = (f"Número: {numero}<br>"
                      f"Fecha: {row['fecha_hora'].date()}<br>"
                      f"Hora: {row['fecha_hora'].time()}<br>"
                      f"Tipo: {tipo}")

        lat, lon = float(row["latitud_n"]), float(row["longitud_w"])
        marker = folium.Marker(
            location=[lat, lon],
            popup=info_popup,
            icon=folium.Icon(color="green" if row["tipo_llamada"] == "saliente" else "blue", icon="phone")
        )

        if numero not in markers_group:
            markers_group[numero] = []
        markers_group[numero].append(marker)

    # Agregar los grupos de marcadores al mapa, pero sin mostrarlos por defecto
    for numero, markers in markers_group.items():
        group = folium.FeatureGroup(name=f"{numero}", show=False)  # show=False -> desmarcado por defecto
        for marker in markers:
            group.add_child(marker)
        mapa.add_child(group)

    folium.LayerControl(collapsed=False).add_to(mapa)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mapa.save(output_path)
    print(f"✅ Mapa interactivo generado en: {output_path}")


def generar_mapa_calor(df, output_path="output/maps/mapa_calor.html"):
    """
    Genera un mapa de calor con las ubicaciones de las llamadas.
    """
    df_clean = df.dropna(subset=["latitud_n", "longitud_w"])
    if df_clean.empty:
        print("⚠️ No hay datos suficientes para generar un mapa de calor.")
        return None

    mapa_calor = folium.Map(location=[df_clean["latitud_n"].mean(), df_clean["longitud_w"].mean()], zoom_start=10)
    heat_data = df_clean[["latitud_n", "longitud_w"]].dropna().values.tolist()
    if not heat_data:
        print("⚠️ No hay coordenadas suficientes para generar un mapa de calor.")
        return None

    HeatMap(heat_data).add_to(mapa_calor)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mapa_calor.save(output_path)
    print(f"🔥 Mapa de calor guardado en: {output_path}")
    return output_path