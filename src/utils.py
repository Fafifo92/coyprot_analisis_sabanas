import logging
import os
import re
import sys
import tkinter as tk

def configurar_logs(text_widget=None):
    """
    Configura el sistema de logging para escribir logs a un archivo y, opcionalmente,
    a un widget de texto en la interfaz gráfica.
    """
    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    LOG_DIR = os.path.join(ROOT_DIR, "logs")
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_FILE = os.path.join(LOG_DIR, "app.log")

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Handler para escribir logs a un archivo (usando UTF-8)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler opcional para escribir logs a un widget de texto
    if text_widget:
        class TextWidgetHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)
                text_widget.config(state=tk.NORMAL)  # Usar tk.NORMAL
                text_widget.insert(tk.END, msg + '\n')
                text_widget.config(state=tk.DISABLED)
                text_widget.see(tk.END)

        text_handler = TextWidgetHandler()
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)

    # Handler para escribir logs a la consola (opcional - usando UTF-8)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

def limpiar_texto(texto):
    """
    Elimina caracteres especiales y espacios innecesarios en un texto.
    """
    if not isinstance(texto, str):
        return ""
    return re.sub(r"[^a-zA-Z0-9@.\s]", "", texto).strip()

def manejar_excepcion(error, logger=None):
    """
    Maneja excepciones y las registra en el log.
    """
    mensaje_error = f"❌ Error: {str(error)}"
    print(mensaje_error)
    if logger:
        logger.error(mensaje_error)

def convertir_a_entero(valor, valor_defecto=0):
    """
    Convierte un valor a entero, manejando errores.
    """
    try:
        return int(valor)
    except (ValueError, TypeError):
        return valor_defecto

def convertir_a_flotante(valor, valor_defecto=0.0):
    """
    Convierte un valor a flotante, manejando errores.
    """
    try:
        return float(valor)
    except (ValueError, TypeError):
        return valor_defecto

if __name__ == "__main__":
    logger = configurar_logs()
    logger.info("🔧 Sistema de logs configurado correctamente.")
    print(limpiar_texto("Texto@ con! caracteres? raros#"))
    print(convertir_a_entero("123"))
    print(convertir_a_flotante("45.67"))