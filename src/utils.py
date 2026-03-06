import logging
import os
import re
import sys
import tkinter as tk

def resource_path(relative_path):
    """
    Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller (.exe).
    
    Args:
        relative_path (str): Ruta relativa desde la raíz del proyecto (ej: "static/assets_img/logo.png")
    """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # En modo desarrollo, la base es la carpeta padre de 'src' (la raíz del proyecto)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    return os.path.join(base_path, relative_path)

def configurar_logs(text_widget=None):
    """
    Configura el sistema de logging para escribir logs a un archivo y, opcionalmente,
    a un widget de texto en la interfaz gráfica.
    """
    # Determinar ruta base para logs
    try:
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except:
        app_dir = os.path.abspath(".")

    LOG_DIR = os.path.join(app_dir, "logs")
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_FILE = os.path.join(LOG_DIR, "app.log")

    logger = logging.getLogger()
    
    # Limpiar handlers previos para evitar duplicados al recargar
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

    # 1. Handler Archivo
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error creando log file: {e}")

    # 2. Handler Consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 3. Handler GUI (Widget Tkinter)
    if text_widget:
        class TextWidgetHandler(logging.Handler):
            def __init__(self, widget):
                super().__init__()
                self.widget = widget
                self.setFormatter(formatter)

            def emit(self, record):
                msg = self.format(record)
                # Usar try/except para evitar crasheos si la ventana se cierra
                try:
                    if self.widget:
                        self.widget.config(state=tk.NORMAL)
                        self.widget.insert(tk.END, msg + '\n')
                        self.widget.config(state=tk.DISABLED)
                        self.widget.see(tk.END)
                except:
                    pass

        gui_handler = TextWidgetHandler(text_widget)
        logger.addHandler(gui_handler)

    return logger

def limpiar_texto(texto):
    """
    Elimina caracteres especiales y espacios innecesarios.
    """
    if not isinstance(texto, str):
        return ""
    # Permite letras, números, espacios, @ y puntos.
    return re.sub(r"[^a-zA-Z0-9@.\s]", "", texto).strip()

def manejar_excepcion(error, logger=None):
    msg = f"❌ Error: {str(error)}"
    print(msg)
    if logger:
        logger.error(msg, exc_info=True)

def convertir_a_entero(valor, valor_defecto=0):
    try:
        return int(float(valor)) # float primero para manejar strings como "5.0"
    except (ValueError, TypeError):
        return valor_defecto

def convertir_a_flotante(valor, valor_defecto=0.0):
    try:
        return float(valor)
    except (ValueError, TypeError):
        return valor_defecto

if __name__ == "__main__":
    # Test rápido
    print(f"Ruta recursos: {resource_path('static')}")
