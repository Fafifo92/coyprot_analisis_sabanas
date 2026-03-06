"""
Widget de log personalizado para Tkinter.

Separa el handler de logging de la GUI principal.
"""
from __future__ import annotations

import logging
import tkinter as tk


class TextWidgetHandler(logging.Handler):
    """
    Handler de logging que escribe en un widget ScrolledText de Tkinter.

    Se ejecuta de forma segura en el hilo principal de la GUI.
    """

    def __init__(self, widget: tk.Text) -> None:
        super().__init__()
        self.widget = widget
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        self.setLevel(logging.INFO)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.widget.config(state=tk.NORMAL)
            self.widget.insert(tk.END, msg + "\n")
            self.widget.config(state=tk.DISABLED)
            self.widget.see(tk.END)
        except Exception:
            pass  # Ventana puede estar cerrada
