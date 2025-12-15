import os
import pandas as pd
import json
import shutil
from jinja2 import Environment, FileSystemLoader
from excel_utils import cargar_datos_excel

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output", "reports")
STATIC_DIR = os.path.join(ROOT_DIR, "static")

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def generar_datos_llamadas_json(df, output_path, nombres_asignados=None):
    if df.empty:
        print("❌ DataFrame está vacío. No se generará call_data.js")
        return

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        call_data = {}
    except Exception as e:
        print(f"❌ Error al crear el directorio: {e}")
        return

    for _, row in df.iterrows():
        numero = row["receptor"] if row["tipo_llamada"] == "saliente" else row["originador"]
        numero_mostrar = f"{numero} ({nombres_asignados[numero]})" if nombres_asignados and numero in nombres_asignados else numero
        hora = row["fecha_hora"].hour

        if numero_mostrar not in call_data:
            call_data[numero_mostrar] = []

        call_data[numero_mostrar].append({
            "fecha_hora": row["fecha_hora"].isoformat(),
            "hora": hora,
            "tipo_llamada": row["tipo_llamada"],
            "latitud": row.get("latitud_n"),
            "longitud": row.get("longitud_w")
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
    base_output = os.path.join(ROOT_DIR, "output", nombre_informe)
    reports_dir = os.path.join(base_output, "reports")
    maps_dir = os.path.join(base_output, "maps")
    graphics_dir = os.path.join(base_output, "graphics")
    data_dir = os.path.join(base_output, "data")
    static_dir = os.path.join(base_output, "static")

    for d in [reports_dir, maps_dir, graphics_dir, data_dir, static_dir]:
        os.makedirs(d, exist_ok=True)

    pdf_dest_path = None
    if pdf_financiero_path and os.path.exists(pdf_financiero_path):
        try:
            pdf_dest_path = os.path.join(data_dir, "reporte_financiero.pdf")
            shutil.copy(pdf_financiero_path, pdf_dest_path)
            print("✅ PDF financiero copiado a la carpeta del informe.")
        except Exception as e:
            print(f"⚠️ No se pudo copiar el PDF financiero: {e}")

    # Copiar archivos JS (asegurar que estén presentes)
    try:
        js_dest = os.path.join(static_dir, "assets_js")
        os.makedirs(js_dest, exist_ok=True)
        shutil.copy(os.path.join(STATIC_DIR, "assets_js", "interactive_maps.js"), os.path.join(js_dest, "interactive_maps.js"))
        shutil.copy(os.path.join(STATIC_DIR, "assets_js", "interactive_charts.js"), os.path.join(js_dest, "interactive_charts.js"))
    except Exception as e:
        print(f"⚠️ Error al copiar archivos JS: {e}")

    template = env.get_template("report_template.html")

    total_llamadas = len(df)
    total_numeros = df['originador'].nunique() + df['receptor'].nunique()
    promedio_llamadas = total_llamadas / total_numeros if total_numeros > 0 else 0

    llamadas_entrantes = {}
    llamadas_salientes = {}
    llamadas_tendencia = []

    for _, row in df.iterrows():
        originador = row['originador']
        receptor = row['receptor']
        tipo_llamada = row['tipo_llamada']

        o_mostrar = f"{originador} ({nombres_asignados[originador]})" if nombres_asignados and originador in nombres_asignados else originador
        r_mostrar = f"{receptor} ({nombres_asignados[receptor]})" if nombres_asignados and receptor in nombres_asignados else receptor

        numero = r_mostrar if tipo_llamada == "saliente" else o_mostrar

        info_llamada = {
            'fecha_hora': row['fecha_hora'],
            'duracion': row['duracion'],
            'ubicacion': f"{row['latitud_n']}, {row['longitud_w']}" if pd.notna(row['latitud_n']) and pd.notna(row['longitud_w']) else "N/A"
        }

        if tipo_llamada == "saliente":
            if r_mostrar not in llamadas_salientes:
                llamadas_salientes[r_mostrar] = {'llamadas': []}
            llamadas_salientes[r_mostrar]['llamadas'].append(info_llamada)
            llamadas_tendencia.append({
                'numero': o_mostrar,
                'fecha_hora': row['fecha_hora'].isoformat(),
                'duracion': row['duracion'],
                'tipo_llamada': tipo_llamada
            })
        elif tipo_llamada == "entrante":
            if o_mostrar not in llamadas_entrantes:
                llamadas_entrantes[o_mostrar] = {'llamadas': []}
            llamadas_entrantes[o_mostrar]['llamadas'].append(info_llamada)
            llamadas_tendencia.append({
                'numero': r_mostrar,
                'fecha_hora': row['fecha_hora'].isoformat(),
                'duracion': row['duracion'],
                'tipo_llamada': tipo_llamada
            })

    numeros_unicos = sorted(set(list(llamadas_entrantes.keys()) + list(llamadas_salientes.keys())))

    html_content = template.render(
        total_llamadas=total_llamadas,
        total_numeros=total_numeros,
        promedio_llamadas=round(promedio_llamadas, 2),
        llamadas_entrantes=llamadas_entrantes,
        llamadas_salientes=llamadas_salientes,
        numeros_unicos=numeros_unicos,
        llamadas=llamadas_tendencia,
        incluir_membrete=incluir_membrete,
        logo_path=logo_path,
        pdf_financiero=bool(pdf_dest_path),
        datos_generales=datos_generales or {}
    )

    informe_path = os.path.join(reports_dir, "informe_llamadas.html")
    with open(informe_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f'✅ Informe HTML guardado en: {informe_path}')

    return base_output

if __name__ == "__main__":
    archivo_excel = "ruta_al_archivo.xlsx"
    df = cargar_datos_excel(archivo_excel)
    if df is not None:
        generar_informe_html(df, nombre_informe="informe_demo")
        generar_datos_llamadas_json(df, output_path="../output/data/call_data.js")