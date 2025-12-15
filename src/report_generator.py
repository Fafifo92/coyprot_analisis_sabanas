import os
import pandas as pd
import json
import shutil
from jinja2 import Environment, FileSystemLoader
# Importamos geo_utils de manera condicional o protegida dentro de la función, 
# pero es mejor importarlas y solo llamarlas si es necesario.
from geo_utils import generar_mapa_interactivo, generar_mapa_calor

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates")
STATIC_DIR = os.path.join(ROOT_DIR, "static")

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def generar_datos_llamadas_json(df, output_path, nombres_asignados=None):
    """
    Genera el archivo JS con los datos para los gráficos interactivos.
    Maneja la ausencia de coordenadas sin romper el código.
    """
    if df.empty:
        print("❌ DataFrame está vacío. No se generará call_data.js")
        return

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        call_data = {}
    except Exception as e:
        print(f"❌ Error al crear el directorio: {e}")
        return

    # Verificar si tenemos columnas de coordenadas en este DF
    tiene_coords = "latitud_n" in df.columns and "longitud_w" in df.columns

    for _, row in df.iterrows():
        # Determinar número y nombre
        tipo = row.get("tipo_llamada", "desconocido")
        originador = row.get("originador", "Desconocido")
        receptor = row.get("receptor", "Desconocido")
        
        numero = receptor if tipo == "saliente" else originador
        
        # Asignar nombre si existe en el diccionario
        nombre_alias = ""
        if nombres_asignados and numero in nombres_asignados:
            nombre_alias = f" ({nombres_asignados[numero]})"
        
        numero_mostrar = f"{numero}{nombre_alias}"
        
        # Obtener hora de manera segura
        try:
            hora = row["fecha_hora"].hour
        except:
            hora = 0

        if numero_mostrar not in call_data:
            call_data[numero_mostrar] = []

        # Extraer coordenadas de forma segura
        lat = row["latitud_n"] if tiene_coords and pd.notna(row["latitud_n"]) else None
        lon = row["longitud_w"] if tiene_coords and pd.notna(row["longitud_w"]) else None

        call_data[numero_mostrar].append({
            "fecha_hora": row["fecha_hora"].isoformat() if pd.notna(row["fecha_hora"]) else "",
            "hora": hora,
            "tipo_llamada": tipo,
            "latitud": lat,
            "longitud": lon
        })

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("const CALL_DATA = ")
            json.dump(call_data, f, indent=4)
            f.write(";")
        print(f"✅ call_data.js generado en: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error al guardar call_data.js: {e}")
        return None

def generar_informe_html(df, nombre_informe, incluir_membrete=False, logo_path=None, pdf_financiero_path=None, nombres_asignados=None, datos_generales=None):
    """
    Genera el informe HTML completo.
    Se adapta dinámicamente si faltan coordenadas u otros datos opcionales.
    """
    base_output = os.path.join(ROOT_DIR, "output", nombre_informe)
    reports_dir = os.path.join(base_output, "reports")
    maps_dir = os.path.join(base_output, "maps")
    graphics_dir = os.path.join(base_output, "graphics")
    data_dir = os.path.join(base_output, "data")
    static_dir = os.path.join(base_output, "static")

    # Crear directorios necesarios
    for d in [reports_dir, maps_dir, graphics_dir, data_dir, static_dir]:
        os.makedirs(d, exist_ok=True)

    # --- 1. Gestión del PDF Financiero ---
    pdf_dest_path = None
    if pdf_financiero_path and os.path.exists(pdf_financiero_path):
        try:
            pdf_dest_path = os.path.join(data_dir, "reporte_financiero.pdf")
            shutil.copy(pdf_financiero_path, pdf_dest_path)
            print("✅ PDF financiero copiado.")
        except Exception as e:
            print(f"⚠️ No se pudo copiar el PDF financiero: {e}")

    # --- 2. Copia de Archivos Estáticos (JS) ---
    try:
        js_dest = os.path.join(static_dir, "assets_js")
        os.makedirs(js_dest, exist_ok=True)
        # Aseguramos que existan en la fuente antes de copiar
        src_map_js = os.path.join(STATIC_DIR, "assets_js", "interactive_maps.js")
        src_chart_js = os.path.join(STATIC_DIR, "assets_js", "interactive_charts.js")
        
        if os.path.exists(src_map_js):
            shutil.copy(src_map_js, os.path.join(js_dest, "interactive_maps.js"))
        if os.path.exists(src_chart_js):
            shutil.copy(src_chart_js, os.path.join(js_dest, "interactive_charts.js"))
    except Exception as e:
        print(f"⚠️ Error copiando scripts JS: {e}")

    # --- 3. Detección de Capacidades (Mapas) ---
    # Verificamos si las columnas existen Y si tienen algún dato válido
    has_coords = False
    if "latitud_n" in df.columns and "longitud_w" in df.columns:
        if df["latitud_n"].notna().any() and df["longitud_w"].notna().any():
            has_coords = True

    # Generar mapas SOLO si hay coordenadas
    if has_coords:
        print("🗺️ Coordenadas detectadas. Generando mapas...")
        try:
            generar_mapa_interactivo(df, os.path.join(maps_dir, "mapa_general.html"))
            generar_mapa_calor(df, os.path.join(maps_dir, "mapa_calor.html"))
        except Exception as e:
            print(f"⚠️ Error generando mapas, se omitirán en el informe: {e}")
            has_coords = False # Desactivar flag si falla la generación
    else:
        print("⚠️ No se detectaron coordenadas válidas. Se omitirá la sección de mapas.")

    # --- 4. Preparación de Datos para la Plantilla ---
    template = env.get_template("report_template.html")

    total_llamadas = len(df)
    # Contamos origen y receptor de forma segura
    uni_orig = df['originador'].dropna().unique() if 'originador' in df.columns else []
    uni_dest = df['receptor'].dropna().unique() if 'receptor' in df.columns else []
    # Unimos listas y eliminamos duplicados
    numeros_unicos_set = set(list(uni_orig) + list(uni_dest))
    total_numeros = len(numeros_unicos_set)
    promedio_llamadas = total_llamadas / total_numeros if total_numeros > 0 else 0

    llamadas_entrantes = {}
    llamadas_salientes = {}
    
    # Lista plana para gráficos
    # (Jinja la usará, pero los gráficos JS usan call_data.js)
    
    for _, row in df.iterrows():
        tipo_llamada = row.get('tipo_llamada', 'desconocido')
        originador = row.get('originador', 'Desconocido')
        receptor = row.get('receptor', 'Desconocido')
        
        # Obtener alias
        alias_orig = f" ({nombres_asignados[originador]})" if nombres_asignados and originador in nombres_asignados else ""
        alias_recep = f" ({nombres_asignados[receptor]})" if nombres_asignados and receptor in nombres_asignados else ""
        
        o_mostrar = f"{originador}{alias_orig}"
        r_mostrar = f"{receptor}{alias_recep}"
        
        # Ubicación string
        ubicacion_str = "N/A"
        if has_coords:
            lat = row.get('latitud_n')
            lon = row.get('longitud_w')
            if pd.notna(lat) and pd.notna(lon):
                ubicacion_str = f"{lat}, {lon}"

        info_llamada = {
            'fecha_hora': row['fecha_hora'],
            'duracion': row.get('duracion', 0),
            'ubicacion': ubicacion_str
        }

        if tipo_llamada == "saliente":
            if r_mostrar not in llamadas_salientes:
                llamadas_salientes[r_mostrar] = {'llamadas': []}
            llamadas_salientes[r_mostrar]['llamadas'].append(info_llamada)
            
        elif tipo_llamada == "entrante":
            if o_mostrar not in llamadas_entrantes:
                llamadas_entrantes[o_mostrar] = {'llamadas': []}
            llamadas_entrantes[o_mostrar]['llamadas'].append(info_llamada)

    # Ordenar números para el filtro
    numeros_unicos_lista = sorted(list(numeros_unicos_set))

    # --- 5. Renderizado ---
    html_content = template.render(
        total_llamadas=total_llamadas,
        total_numeros=total_numeros,
        promedio_llamadas=round(promedio_llamadas, 2),
        llamadas_entrantes=llamadas_entrantes,
        llamadas_salientes=llamadas_salientes,
        numeros_unicos=numeros_unicos_lista,
        incluir_membrete=incluir_membrete,
        logo_path=logo_path,
        pdf_financiero=bool(pdf_dest_path),
        datos_generales=datos_generales or {},
        has_coords=has_coords # <--- Flag Clave para la plantilla
    )

    informe_path = os.path.join(reports_dir, "informe_llamadas.html")
    with open(informe_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f'✅ Informe HTML generado exitosamente en: {informe_path}')
    return base_output