import os
import pandas as pd
import json
import shutil
from jinja2 import Environment, FileSystemLoader
# Importamos las funciones de mapas (incluyendo el nuevo Timeline de Plotly)
from geo_utils import generar_mapa_agrupado, generar_mapa_rutas, generar_mapa_calor
# Importamos la lógica geográfica mejorada
from colombia_data import obtener_ubicacion_completa

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates")
STATIC_DIR = os.path.join(ROOT_DIR, "static")

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def obtener_nombre_mostrado(numero, nombres_asignados):
    """Garantiza formato 'Número (Alias)' consistente."""
    numero_str = str(numero).strip()
    if nombres_asignados and numero_str in nombres_asignados:
        return f"{numero_str} ({nombres_asignados[numero_str]})"
    return numero_str

def obtener_top_frecuentes(df, columna_numero, nombres_asignados, top_n=5):
    """Calcula Top 5 para resumen."""
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
    """Genera call_data.js para los gráficos interactivos."""
    if df.empty:
        return

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        call_data = {}
        tiene_coords = "latitud_n" in df.columns and "longitud_w" in df.columns

        for _, row in df.iterrows():
            tipo = row.get("tipo_llamada", "desconocido")
            originador = str(row.get("originador", "Desconocido"))
            receptor = str(row.get("receptor", "Desconocido"))
            
            numero_clave = receptor if tipo == "saliente" else originador
            numero_mostrar = obtener_nombre_mostrado(numero_clave, nombres_asignados)
            
            try: hora = row["fecha_hora"].hour
            except: hora = 0

            if numero_mostrar not in call_data:
                call_data[numero_mostrar] = []

            lat = row["latitud_n"] if tiene_coords and pd.notna(row["latitud_n"]) else None
            lon = row["longitud_w"] if tiene_coords and pd.notna(row["longitud_w"]) else None

            call_data[numero_mostrar].append({
                "numero": numero_mostrar,
                "fecha_hora": row["fecha_hora"].isoformat() if pd.notna(row["fecha_hora"]) else "",
                "hora": hora,
                "tipo_llamada": tipo,
                "latitud": lat,
                "longitud": lon
            })

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("const CALL_DATA = ")
            json.dump(call_data, f, indent=4)
            f.write(";")
    except Exception as e:
        print(f"❌ Error generando JSON: {e}")

def generar_informe_html(df, nombre_informe, incluir_membrete=False, logo_path=None, lista_adjuntos=None, nombres_asignados=None, datos_generales=None):
    """Genera el informe HTML completo con lógica geográfica."""
    base_output = os.path.join(ROOT_DIR, "output", nombre_informe)
    reports_dir = os.path.join(base_output, "reports")
    maps_dir = os.path.join(base_output, "maps")
    graphics_dir = os.path.join(base_output, "graphics")
    data_dir = os.path.join(base_output, "data")
    static_dir = os.path.join(base_output, "static")

    for d in [reports_dir, maps_dir, graphics_dir, data_dir, static_dir]:
        os.makedirs(d, exist_ok=True)

    # 1. Adjuntos
    archivos_procesados = []
    if lista_adjuntos:
        print(f"📎 Procesando {len(lista_adjuntos)} adjuntos...")
        for adjunto in lista_adjuntos:
            try:
                shutil.copy(adjunto['ruta'], os.path.join(data_dir, adjunto['nombre_archivo']))
                archivos_procesados.append({
                    "categoria": adjunto['categoria'],
                    "nombre": adjunto['nombre_archivo'],
                    "ruta_relativa": f"../data/{adjunto['nombre_archivo']}"
                })
            except: pass

    # 2. Recursos Estáticos
    try:
        js_dest = os.path.join(static_dir, "assets_js")
        img_dest = os.path.join(static_dir, "assets_img")
        os.makedirs(js_dest, exist_ok=True)
        os.makedirs(img_dest, exist_ok=True)
        
        for js in ["interactive_maps.js", "interactive_charts.js"]:
            src = os.path.join(STATIC_DIR, "assets_js", js)
            if os.path.exists(src): shutil.copy(src, os.path.join(js_dest, js))
            
        if logo_path and os.path.exists(logo_path): shutil.copy(logo_path, os.path.join(img_dest, "logo.png"))
        src_info = os.path.join(STATIC_DIR, "assets_img", "info.png")
        if os.path.exists(src_info): shutil.copy(src_info, os.path.join(img_dest, "info.png"))
    except Exception as e:
        print(f"⚠️ Error assets: {e}")

    # 3. Mapas (Generación Separada)
    has_coords = False
    if "latitud_n" in df.columns and "longitud_w" in df.columns:
        if df["latitud_n"].notna().any():
            has_coords = True
            try:
                print("🗺️ Generando mapas...")
                # Mapas Generales (Para pestaña 'Mapas')
                generar_mapa_agrupado(df, os.path.join(maps_dir, "mapa_agrupado.html"), nombres_asignados)
                generar_mapa_calor(df, os.path.join(maps_dir, "mapa_calor.html"))
                
                # Mapa de Recorrido/Timeline (Para nueva pestaña 'Recorrido')
                # IMPORTANTE: Se guarda como 'mapa_recorrido.html' para coincidir con el template
                generar_mapa_rutas(df, os.path.join(maps_dir, "mapa_recorrido.html"), nombres_asignados)
            except Exception as e:
                print(f"⚠️ Error mapas: {e}")

    # 4. Datos del Reporte
    total_llamadas = len(df)
    uni_orig = df['originador'].dropna().unique() if 'originador' in df.columns else []
    uni_dest = df['receptor'].dropna().unique() if 'receptor' in df.columns else []
    numeros_brutos = set(list(uni_orig) + list(uni_dest))
    numeros_unicos_lista = sorted([obtener_nombre_mostrado(n, nombres_asignados) for n in numeros_brutos])
    promedio_llamadas = total_llamadas / len(numeros_brutos) if numeros_brutos else 0

    top_entrantes = obtener_top_frecuentes(df[df['tipo_llamada'] == 'entrante'], 'originador', nombres_asignados)
    top_salientes = obtener_top_frecuentes(df[df['tipo_llamada'] == 'saliente'], 'receptor', nombres_asignados)

    # Preparar Tablas y Geografía
    llamadas_entrantes = {}
    llamadas_salientes = {}
    
    # Contenedor temporal para armar el mapa de dependencias (Depto -> Municipios)
    mapa_geografico_temp = {}

    print("📍 Calculando geografía completa (Depto/Muni)...")

    for _, row in df.iterrows():
        tipo = row.get('tipo_llamada', 'desconocido')
        originador = str(row.get('originador', 'Desconocido'))
        receptor = str(row.get('receptor', 'Desconocido'))
        
        o_show = obtener_nombre_mostrado(originador, nombres_asignados)
        r_show = obtener_nombre_mostrado(receptor, nombres_asignados)
        
        # --- LÓGICA DE UBICACIÓN ---
        loc_coords = "N/A"
        depto = "Desconocido"
        muni = "Desconocido"
        
        if has_coords and pd.notna(row.get('latitud_n')) and pd.notna(row.get('longitud_w')):
            lat, lon = row.get('latitud_n'), row.get('longitud_w')
            loc_coords = f"{lat}, {lon}"
            
            # Calculamos Depto y Municipio usando colombia_data
            d_calc, m_calc = obtener_ubicacion_completa(lat, lon)
            
            # Guardamos para el filtro en cascada si son válidos
            if d_calc not in ["Desconocido", "Otros / Rural"] and m_calc not in ["Desconocido", "Zona Rural"]:
                if d_calc not in mapa_geografico_temp:
                    mapa_geografico_temp[d_calc] = set()
                mapa_geografico_temp[d_calc].add(m_calc)
            
            depto, muni = d_calc, m_calc

        info = {
            'fecha_hora': row['fecha_hora'], 
            'duracion': row.get('duracion', 0), 
            'ubicacion_coords': loc_coords,
            'departamento': depto,
            'municipio': muni
        }

        if tipo == "saliente":
            if r_show not in llamadas_salientes: llamadas_salientes[r_show] = {'llamadas': []}
            llamadas_salientes[r_show]['llamadas'].append(info)
        elif tipo == "entrante":
            if o_show not in llamadas_entrantes: llamadas_entrantes[o_show] = {'llamadas': []}
            llamadas_entrantes[o_show]['llamadas'].append(info)

    # --- PREPARAR DATOS PARA EL HTML (JSON SAFE) ---
    # Convertimos el mapa de Sets a mapa de Listas ordenadas
    mapa_dep_mun = {}
    for d, m_set in mapa_geografico_temp.items():
        mapa_dep_mun[d] = sorted(list(m_set))
        
    lista_departamentos = sorted(list(mapa_dep_mun.keys()))
    
    # Lista plana de todos los municipios para el filtro simple
    todos_municipios = set()
    for m_list in mapa_dep_mun.values():
        todos_municipios.update(m_list)
    lista_municipios = sorted(list(todos_municipios))

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
            has_coords=has_coords,
            # NUEVAS VARIABLES PARA FILTROS
            lista_municipios=lista_municipios,
            lista_departamentos=lista_departamentos,
            mapa_dep_mun=mapa_dep_mun # Diccionario limpio para JavaScript
        )

        informe_path = os.path.join(reports_dir, "informe_llamadas.html")
        with open(informe_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f'✅ Informe generado: {informe_path}')
        return base_output
        
    except Exception as e:
        print(f"❌ Error renderizando HTML: {e}")
        return base_output