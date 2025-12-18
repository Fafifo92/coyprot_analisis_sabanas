import os
import pandas as pd
import json
import shutil
from jinja2 import Environment, FileSystemLoader
# Importamos las 3 funciones de mapas para generarlos durante el reporte
from geo_utils import generar_mapa_agrupado, generar_mapa_rutas, generar_mapa_calor

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates")
STATIC_DIR = os.path.join(ROOT_DIR, "static")

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def obtener_nombre_mostrado(numero, nombres_asignados):
    """
    Función auxiliar para garantizar que el formato 'Número (Alias)' 
    sea idéntico en todas partes (HTML, Gráficos, JSON).
    """
    numero_str = str(numero).strip()
    if nombres_asignados and numero_str in nombres_asignados:
        return f"{numero_str} ({nombres_asignados[numero_str]})"
    return numero_str

def obtener_top_frecuentes(df, columna_numero, nombres_asignados, top_n=5):
    """
    Calcula los números más frecuentes para las cajas de resumen del reporte.
    """
    if df.empty or columna_numero not in df.columns:
        return []
    
    conteo = df[columna_numero].value_counts().head(top_n)
    resultado = []
    for numero, cantidad in conteo.items():
        nombre_display = obtener_nombre_mostrado(numero, nombres_asignados)
        resultado.append({
            'nombre': nombre_display,
            'frecuencia': cantidad
        })
    return resultado

def generar_datos_llamadas_json(df, output_path, nombres_asignados=None):
    """
    Genera el archivo call_data.js.
    Incluye el campo 'numero' con alias para el tooltip interactivo.
    Detecta si hay coordenadas (originales o inferidas por municipio) para incluir el pin en el tooltip.
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

    # Verificamos si existen las columnas, incluso si fueron rellenadas por inferencia
    tiene_coords = "latitud_n" in df.columns and "longitud_w" in df.columns

    for _, row in df.iterrows():
        # Determinar tipo y participantes
        tipo = row.get("tipo_llamada", "desconocido")
        originador = str(row.get("originador", "Desconocido"))
        receptor = str(row.get("receptor", "Desconocido"))
        
        # Identificar el número principal de esta fila para agrupar en el gráfico
        numero_clave = receptor if tipo == "saliente" else originador
        
        # Nombre visual (ej: "300123 (Juan)")
        numero_mostrar = obtener_nombre_mostrado(numero_clave, nombres_asignados)
        
        try:
            hora = row["fecha_hora"].hour
        except:
            hora = 0

        if numero_mostrar not in call_data:
            call_data[numero_mostrar] = []

        # Extraer coordenadas (si existen y no son nulas)
        lat = row["latitud_n"] if tiene_coords and pd.notna(row["latitud_n"]) else None
        lon = row["longitud_w"] if tiene_coords and pd.notna(row["longitud_w"]) else None

        call_data[numero_mostrar].append({
            "numero": numero_mostrar, # Campo crítico para el tooltip
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
        print(f"✅ call_data.js generado correctamente en: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error al guardar call_data.js: {e}")
        return None

def generar_informe_html(df, nombre_informe, incluir_membrete=False, logo_path=None, lista_adjuntos=None, nombres_asignados=None, datos_generales=None):
    """
    Genera el informe HTML completo.
    Coordina la creación de los 3 tipos de mapas si hay coordenadas (originales o inferidas).
    """
    base_output = os.path.join(ROOT_DIR, "output", nombre_informe)
    reports_dir = os.path.join(base_output, "reports")
    maps_dir = os.path.join(base_output, "maps")
    graphics_dir = os.path.join(base_output, "graphics")
    data_dir = os.path.join(base_output, "data")
    static_dir = os.path.join(base_output, "static")

    # Crear estructura de directorios
    for d in [reports_dir, maps_dir, graphics_dir, data_dir, static_dir]:
        os.makedirs(d, exist_ok=True)

    # --- 1. Procesar Adjuntos (Multi-PDF) ---
    archivos_procesados = []
    if lista_adjuntos:
        print(f"📎 Procesando {len(lista_adjuntos)} adjuntos...")
        for adjunto in lista_adjuntos:
            origen = adjunto['ruta']
            nombre_archivo = adjunto['nombre_archivo']
            categoria = adjunto['categoria']
            destino = os.path.join(data_dir, nombre_archivo)
            
            try:
                if os.path.exists(origen):
                    shutil.copy(origen, destino)
                    archivos_procesados.append({
                        "categoria": categoria,
                        "nombre": nombre_archivo,
                        "ruta_relativa": f"../data/{nombre_archivo}"
                    })
                else:
                    print(f"  ⚠️ Archivo no encontrado: {origen}")
            except Exception as e:
                print(f"  ❌ Error copiando adjunto: {e}")

    # --- 2. Copiar Recursos Estáticos ---
    try:
        js_dest = os.path.join(static_dir, "assets_js")
        img_dest = os.path.join(static_dir, "assets_img")
        os.makedirs(js_dest, exist_ok=True)
        os.makedirs(img_dest, exist_ok=True)
        
        # Copiar JS originales
        src_map_js = os.path.join(STATIC_DIR, "assets_js", "interactive_maps.js")
        src_chart_js = os.path.join(STATIC_DIR, "assets_js", "interactive_charts.js")
        
        if os.path.exists(src_map_js): shutil.copy(src_map_js, os.path.join(js_dest, "interactive_maps.js"))
        if os.path.exists(src_chart_js): shutil.copy(src_chart_js, os.path.join(js_dest, "interactive_charts.js"))
        
        # Copiar Logos e Imágenes
        if logo_path and os.path.exists(logo_path): shutil.copy(logo_path, os.path.join(img_dest, "logo.png"))
        src_info_img = os.path.join(STATIC_DIR, "assets_img", "info.png")
        if os.path.exists(src_info_img): shutil.copy(src_info_img, os.path.join(img_dest, "info.png"))

    except Exception as e:
        print(f"⚠️ Error recursos estáticos: {e}")

    # --- 3. Detección de Coordenadas y Generación de Mapas ---
    has_coords = False
    if "latitud_n" in df.columns and "longitud_w" in df.columns:
        # Verificamos si hay ALGUN dato válido (ya sea GPS o inferido)
        if df["latitud_n"].notna().any() and df["longitud_w"].notna().any():
            has_coords = True

    if has_coords:
        try:
            print("🗺️ Generando set completo de mapas interactivos...")
            
            # 1. Mapa Agrupado (Clusters)
            generar_mapa_agrupado(df, os.path.join(maps_dir, "mapa_agrupado.html"), nombres_asignados)
            
            # 2. Mapa de Rutas (Cronológico)
            generar_mapa_rutas(df, os.path.join(maps_dir, "mapa_rutas.html"), nombres_asignados)
            
            # 3. Mapa de Calor (Densidad)
            generar_mapa_calor(df, os.path.join(maps_dir, "mapa_calor.html"))
            
        except Exception as e:
            print(f"⚠️ Error generando mapas: {e}")
            has_coords = False

    # --- 4. Preparar Datos para el Reporte HTML ---
    total_llamadas = len(df)
    uni_orig = df['originador'].dropna().unique() if 'originador' in df.columns else []
    uni_dest = df['receptor'].dropna().unique() if 'receptor' in df.columns else []
    numeros_brutos = set(list(uni_orig) + list(uni_dest))
    
    numeros_unicos_lista = sorted([obtener_nombre_mostrado(n, nombres_asignados) for n in numeros_brutos])
    promedio_llamadas = total_llamadas / len(numeros_brutos) if numeros_brutos else 0

    # Calcular Tops (Cajas de resumen)
    df_entrantes = df[df['tipo_llamada'] == 'entrante']
    top_entrantes = obtener_top_frecuentes(df_entrantes, 'originador', nombres_asignados)

    df_salientes = df[df['tipo_llamada'] == 'saliente']
    top_salientes = obtener_top_frecuentes(df_salientes, 'receptor', nombres_asignados)

    # Preparar Tablas de Detalle
    llamadas_entrantes = {}
    llamadas_salientes = {}
    
    for _, row in df.iterrows():
        tipo = row.get('tipo_llamada', 'desconocido')
        originador = str(row.get('originador', 'Desconocido'))
        receptor = str(row.get('receptor', 'Desconocido'))
        
        o_show = obtener_nombre_mostrado(originador, nombres_asignados)
        r_show = obtener_nombre_mostrado(receptor, nombres_asignados)
        
        # Determinar ubicación para la tabla (Coords para botón Google Maps)
        loc = "N/A"
        if has_coords and pd.notna(row.get('latitud_n')) and pd.notna(row.get('longitud_w')):
             loc = f"{row.get('latitud_n')}, {row.get('longitud_w')}"

        info = {
            'fecha_hora': row['fecha_hora'], 
            'duracion': row.get('duracion', 0), 
            'ubicacion': loc
        }

        if tipo == "saliente":
            if r_show not in llamadas_salientes: llamadas_salientes[r_show] = {'llamadas': []}
            llamadas_salientes[r_show]['llamadas'].append(info)
        elif tipo == "entrante":
            if o_show not in llamadas_entrantes: llamadas_entrantes[o_show] = {'llamadas': []}
            llamadas_entrantes[o_show]['llamadas'].append(info)

    # --- 5. Renderizar Plantilla Jinja2 ---
    try:
        template = env.get_template("report_template.html")
        html_content = template.render(
            total_llamadas=total_llamadas,
            total_numeros=len(numeros_brutos),
            promedio_llamadas=round(promedio_llamadas, 2),
            llamadas_entrantes=llamadas_entrantes,
            llamadas_salientes=llamadas_salientes,
            numeros_unicos=numeros_unicos_lista,
            top_entrantes=top_entrantes,
            top_salientes=top_salientes,
            incluir_membrete=incluir_membrete,
            logo_path=logo_path,
            adjuntos=archivos_procesados,
            datos_generales=datos_generales or {},
            has_coords=has_coords # Esto activa las pestañas de mapas en el HTML
        )

        informe_path = os.path.join(reports_dir, "informe_llamadas.html")
        with open(informe_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f'✅ Informe HTML generado exitosamente: {informe_path}')
        return base_output
        
    except Exception as e:
        print(f"❌ Error renderizando HTML: {e}")
        return base_output