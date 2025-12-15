import os
from tkinter import Tk, filedialog
from excel_utils import cargar_datos_excel
from report_generator import generar_informe_html, generar_datos_llamadas_json
from geo_utils import generar_mapa_interactivo, generar_mapa_calor
from graphics_utils import generar_grafico_top_llamadas, generar_grafico_horario_llamadas
from utils import configurar_logs
import shutil

# Configuración de directorios
SRC_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(SRC_DIR)
STATIC_DIR = os.path.join(ROOT_DIR, "static")

def obtener_ruta_output(base_dir, subdir, archivo):
    ruta = os.path.join(base_dir, subdir)
    os.makedirs(ruta, exist_ok=True)
    return os.path.join(ruta, archivo)

def seleccionar_archivo():
    Tk().withdraw()
    archivo = filedialog.askopenfilename(filetypes=[("Archivos Excel", "*.xlsx")])
    if not archivo:
        print("❌ No se seleccionó ningún archivo. Saliendo...")
        exit()
    return archivo

def main():
    logger = configurar_logs()
    logger.info("🚀 Iniciando análisis de llamadas")

    archivo_excel = seleccionar_archivo()
    nombre_informe = input("📝 Nombre del informe (carpeta destino): ").strip().replace(" ", "_")

    df = cargar_datos_excel(archivo_excel)
    if df is None or df.empty:
        logger.error("❌ No se pudo cargar el archivo de datos.")
        return

    if "tipo_llamada" not in df.columns or df["tipo_llamada"].nunique() < 2:
        logger.error("❌ Se requieren datos de llamadas 'entrantes' y 'salientes'.")
        return

    logger.info("📊 Generando informe HTML...")
    base_dir = generar_informe_html(df, nombre_informe, incluir_membrete=True, logo_path=os.path.join(STATIC_DIR, "logo.png"))

    logger.info("🗺️ Generando mapas...")
    generar_mapa_interactivo(df, obtener_ruta_output(base_dir, "maps", "mapa_general.html"))
    generar_mapa_calor(df, obtener_ruta_output(base_dir, "maps", "mapa_calor.html"))

    logger.info("📈 Generando gráficos...")
    generar_grafico_top_llamadas(df[df["tipo_llamada"] == "entrante"], "originador", "Top Llamadas Recibidas",
                                  obtener_ruta_output(base_dir, "graphics", "top_llamadas_recibidas.png"))
    generar_grafico_top_llamadas(df[df["tipo_llamada"] == "saliente"], "receptor", "Top Llamadas Realizadas",
                                  obtener_ruta_output(base_dir, "graphics", "top_llamadas_realizadas.png"))
    generar_grafico_horario_llamadas(df, obtener_ruta_output(base_dir, "graphics", "grafico_horario_llamadas.png"))

    logger.info("📁 Guardando datos JS dinámicos...")
    generar_datos_llamadas_json(df, output_path=obtener_ruta_output(base_dir, "data", "call_data.js"))

    logger.info("📦 Copiando archivos estáticos...")
    os.makedirs(os.path.join(base_dir, "static", "assets_js"), exist_ok=True)
    shutil.copy(os.path.join(STATIC_DIR, "js", "interactive_maps.js"), os.path.join(base_dir, "static", "assets_js", "interactive_maps.js"))
    shutil.copy(os.path.join(STATIC_DIR, "js", "interactive_charts.js"), os.path.join(base_dir, "static", "assets_js", "interactive_charts.js"))
    shutil.copy(os.path.join(STATIC_DIR, "logo.png"), os.path.join(base_dir, "static", "assets_img", "logo.png"))
    shutil.copy(os.path.join(STATIC_DIR, "info.png"), os.path.join(base_dir, "static", "assets_img", "info.png"))

    logger.info("✅ Análisis completo. Informe generado en: %s", base_dir)
    print("✅ Proceso finalizado. El informe, mapas y gráficos han sido guardados en:", base_dir)

if __name__ == "__main__":
    main()