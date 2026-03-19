"""
Aplicación GUI principal.

Responsabilidad exclusiva: presentación y captura de entrada del usuario.
Toda la lógica de negocio se delega a los servicios inyectados.
"""
from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

import pandas as pd
from ttkthemes import ThemedTk

from config.constants import (
    COL_CALL_TYPE,
    GUI_GEOMETRY,
    GUI_LOG_FONT,
    GUI_MIN_SIZE,
    GUI_THEME,
    PDF_CATEGORIES,
    QUEUE_POLL_MS,
)
from config.settings import settings
from core.models import (
    CallStats,
    CaseMetadata,
    PdfAttachment,
    PdfExportConfig,
    ReportConfig,
    RouteMapMode,
)
from reports.report_generator import ReportGenerator
from services.data_processing_service import DataProcessingService
from services.geocoding_service import GeocodingService
from services.upload_service import UploadService
from ui.dialogs.column_mapper import ColumnMapperDialog
from ui.dialogs.sheet_mapper import SheetColumnMapperDialog
from ui.widgets import TextWidgetHandler

logger = logging.getLogger(__name__)

# ── Colores del semáforo ──────────────────────────────────────────────────────
_SEMAPHORE_COLORS = {
    "green": "#28a745",
    "yellow": "#ffc107",
    "red": "#dc3545",
    "gray": "#6c757d",
}


class CallAnalyzerApp(ThemedTk):
    """
    Ventana principal del Analizador de Llamadas.

    Principio S: solo maneja la UI (threading, eventos, widgets).
    Toda la lógica de datos se delega a los servicios.
    Principio D: los servicios se inyectan para facilitar pruebas.
    """

    def __init__(
        self,
        data_service: Optional[DataProcessingService] = None,
        geocoding_service: Optional[GeocodingService] = None,
        report_generator: Optional[ReportGenerator] = None,
        upload_service: Optional[UploadService] = None,
    ) -> None:
        super().__init__(theme=GUI_THEME)
        self.title(settings.app_title)
        self.geometry(GUI_GEOMETRY)
        self.minsize(*GUI_MIN_SIZE)

        # ── Servicios (inyección de dependencias) ─────────────────────────────
        self._data_svc = data_service or DataProcessingService()
        self._geo_svc = geocoding_service or GeocodingService.from_paths(
            cell_db_path=settings.cell_db_path,
            muni_db_path=settings.municipalities_db_path,
        )
        self._report_gen = report_generator or ReportGenerator(
            geocoding_service=self._geo_svc
        )
        self._upload_svc = upload_service or UploadService()

        # ── Estado de la aplicación ───────────────────────────────────────────
        self._df: Optional[pd.DataFrame] = None
        self._raw_df: Optional[pd.DataFrame] = None
        self._raw_sheets: Optional[dict[str, pd.DataFrame]] = None
        self._work_queue: queue.Queue = queue.Queue()
        self._is_busy = False

        # ── Estado multi-archivo ──────────────────────────────────────────────
        # Cada entrada: {name, path, types, rows, raw_sheets, sheet_configs, processed_df}
        self._loaded_files: list[dict] = []
        self._accumulated_df: Optional[pd.DataFrame] = None
        self._file_counter: int = 0  # IDs únicos para treeview
        self._analysis_dirty: bool = False  # True cuando hay datos sin analizar

        # ── Variables Tkinter ─────────────────────────────────────────────────
        self._file_path = tk.StringVar()
        self._report_name = tk.StringVar(value="Informe_Llamadas")
        self._include_logo = tk.BooleanVar(value=True)
        self._upload_ftp = tk.BooleanVar(value=False)
        self._aliases: dict[str, str] = {}
        self._case_metadata = CaseMetadata.with_defaults()
        self._pdf_list: list[PdfAttachment] = []

        # ── Estado PDF ─────────────────────────────────────────────────────
        self._report_base_dir: Optional[Path] = None
        self._last_ftp_url: str = ""
        self._pdf_route_mode = tk.StringVar(value="consolidated")

        # ── Inicializar UI ────────────────────────────────────────────────────
        self._log_widget: Optional[scrolledtext.ScrolledText] = None
        self._create_widgets()
        self._setup_logging()

        logger.info("Aplicación lista. Versión %s", settings.app_version)
        self.after(QUEUE_POLL_MS, self._poll_queue)

    # ── Setup de logging ──────────────────────────────────────────────────────

    def _setup_logging(self) -> None:
        """Configura el logging hacia archivo, consola y widget GUI."""
        settings.ensure_dirs()
        log_path = settings.logs_dir / settings.log_filename

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

        fmt = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )

        file_handler = logging.FileHandler(str(log_path), encoding="utf-8", mode="a")
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        root_logger.addHandler(console_handler)

        if self._log_widget:
            gui_handler = TextWidgetHandler(self._log_widget)
            root_logger.addHandler(gui_handler)

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _create_widgets(self) -> None:
        outer = ttk.Frame(self, padding="15")
        outer.pack(expand=True, fill=tk.BOTH)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Canvas scrollable para todo el contenido
        self._canvas = tk.Canvas(outer, highlightthickness=0)
        v_scroll = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=v_scroll.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        main = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=main, anchor="nw"
        )
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)

        self._build_file_section(main)
        self._build_attachments_section(main)
        self._build_options_and_export(main)
        self._build_log_section(main)

        # Ajustar scrollregion y ancho del frame interno
        def _on_frame_configure(event):
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))

        def _on_canvas_configure(event):
            self._canvas.itemconfig(self._canvas_window, width=event.width)

        main.bind("<Configure>", _on_frame_configure)
        self._canvas.bind("<Configure>", _on_canvas_configure)

        # Scroll con rueda del mouse
        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self._canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _build_file_section(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=1)

        # ── Panel de archivos cargados ────────────────────────────────────────
        f_load = ttk.LabelFrame(
            top, text="Archivos Excel / CSV", padding="10"
        )
        f_load.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        f_load.grid_columnconfigure(0, weight=1)

        # Treeview con archivos cargados
        self._tree_files = ttk.Treeview(
            f_load,
            columns=("archivo", "tipos", "filas"),
            show="headings",
            height=3,
        )
        self._tree_files.heading("archivo", text="Archivo")
        self._tree_files.column("archivo", width=180, anchor="w")
        self._tree_files.heading("tipos", text="Datos Detectados")
        self._tree_files.column("tipos", width=160, anchor="w")
        self._tree_files.heading("filas", text="Registros")
        self._tree_files.column("filas", width=70, anchor="center")
        self._tree_files.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        scrol_files = ttk.Scrollbar(
            f_load, orient="vertical", command=self._tree_files.yview
        )
        self._tree_files.configure(yscrollcommand=scrol_files.set)
        scrol_files.grid(row=0, column=1, sticky="ns")

        # Botones
        btn_frame = ttk.Frame(f_load)
        btn_frame.grid(row=0, column=2, sticky="n", padx=(5, 0))

        self._btn_load = ttk.Button(
            btn_frame, text="Agregar Archivo", command=self._on_load_file
        )
        self._btn_load.pack(fill="x", pady=2)

        self._btn_edit_file = ttk.Button(
            btn_frame, text="Editar Columnas", command=self._on_edit_file,
            state=tk.DISABLED,
        )
        self._btn_edit_file.pack(fill="x", pady=2)

        self._btn_remove_file = ttk.Button(
            btn_frame, text="Eliminar Archivo", command=self._on_remove_file,
            state=tk.DISABLED,
        )
        self._btn_remove_file.pack(fill="x", pady=2)

        self._btn_clear_files = ttk.Button(
            btn_frame, text="Limpiar Todo", command=self._on_clear_files
        )
        self._btn_clear_files.pack(fill="x", pady=2)

        self._btn_analyze = ttk.Button(
            btn_frame,
            text="Realizar Análisis",
            command=self._on_run_analysis,
            state=tk.DISABLED,
        )
        self._btn_analyze.pack(fill="x", pady=(8, 2))

        # ── Panel de estado de datos ──────────────────────────────────────────
        f_status = ttk.LabelFrame(top, text="Estado de Datos", padding="10")
        f_status.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # Indicadores por tipo de dato
        self._status_indicators: dict[str, dict] = {}
        for idx, (tipo, label) in enumerate(
            [("entrante", "Entrantes"), ("saliente", "Salientes"), ("datos", "Datos")]
        ):
            row_f = ttk.Frame(f_status)
            row_f.pack(fill="x", pady=2)

            canvas = tk.Canvas(row_f, width=14, height=14, highlightthickness=0)
            canvas.pack(side="left", padx=(0, 6))
            light = canvas.create_oval(2, 2, 12, 12, fill="#6c757d", outline="#6c757d")

            lbl = ttk.Label(row_f, text=f"{label}: 0", font=("Arial", 9))
            lbl.pack(side="left")

            self._status_indicators[tipo] = {
                "canvas": canvas,
                "light": light,
                "label": lbl,
                "count": 0,
            }

        ttk.Separator(f_status, orient="horizontal").pack(fill="x", pady=6)

        self._lbl_total = ttk.Label(
            f_status, text="Total: 0 registros", font=("Arial", 9, "bold")
        )
        self._lbl_total.pack(anchor="w")

        self._lbl_files_count = ttk.Label(
            f_status, text="Archivos: 0", font=("Arial", 9)
        )
        self._lbl_files_count.pack(anchor="w")

    def _build_attachments_section(self, parent: ttk.Frame) -> None:
        f_adj = ttk.LabelFrame(parent, text="Adjuntos (PDF)", padding="10")
        f_adj.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        f_adj.grid_columnconfigure(0, weight=1)

        self._tree_adj = ttk.Treeview(
            f_adj, columns=("cat", "arch"), show="headings", height=3
        )
        self._tree_adj.heading("cat", text="Categoría")
        self._tree_adj.column("cat", width=150, anchor="center")
        self._tree_adj.heading("arch", text="Archivo")
        self._tree_adj.column("arch", width=550, anchor="w")
        self._tree_adj.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=5)

        scrol = ttk.Scrollbar(f_adj, orient="vertical", command=self._tree_adj.yview)
        self._tree_adj.configure(yscrollcommand=scrol.set)
        scrol.grid(row=0, column=1, rowspan=2, sticky="ns")

        btn_frame = ttk.Frame(f_adj)
        btn_frame.grid(row=0, column=2, sticky="n", padx=10)
        self._btn_add_pdf = ttk.Button(
            btn_frame, text="Agregar", command=self._on_add_pdf
        )
        self._btn_add_pdf.pack(fill="x", pady=2)
        self._btn_del_pdf = ttk.Button(
            btn_frame, text="Quitar", command=self._on_remove_pdf
        )
        self._btn_del_pdf.pack(fill="x", pady=2)

    def _build_options_and_export(self, parent: ttk.Frame) -> None:
        # Opciones
        f_ops = ttk.LabelFrame(parent, text="Procesamiento", padding="10")
        f_ops.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        self._btn_aliases = ttk.Button(
            f_ops,
            text="Asignar Nombres/Alias",
            command=self._on_assign_aliases,
            state=tk.DISABLED,
        )
        self._btn_aliases.pack(fill="x", pady=5, ipady=3)

        self._btn_case_data = ttk.Button(
            f_ops,
            text="Datos del Caso",
            command=self._on_edit_case_data,
            state=tk.DISABLED,
        )
        self._btn_case_data.pack(fill="x", pady=5, ipady=3)

        # Exportar
        f_exp = ttk.LabelFrame(parent, text="Generar Informe", padding="10")
        f_exp.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)

        f_name = ttk.Frame(f_exp)
        f_name.pack(fill="x", pady=5)
        ttk.Label(f_name, text="Nombre Carpeta:").pack(side="left")
        ttk.Entry(f_name, textvariable=self._report_name).pack(
            side="left", fill="x", expand=True, padx=10
        )

        f_chk = ttk.Frame(f_exp)
        f_chk.pack(fill="x", pady=5)
        ttk.Checkbutton(f_chk, text="Incluir Membretes", variable=self._include_logo).pack(
            side="left", padx=10
        )
        ftp_chk = ttk.Checkbutton(
            f_chk, text="Subir a FTP", variable=self._upload_ftp
        )
        ftp_chk.pack(side="left", padx=10)
        if not settings.ftp_configured():
            ftp_chk.configure(state=tk.DISABLED)
            self._upload_ftp.set(False)

        self._btn_export = ttk.Button(
            f_exp,
            text="Generar y Exportar Informe",
            command=self._on_export,
            state=tk.DISABLED,
        )
        self._btn_export.pack(fill="x", pady=10, ipady=5)
        try:
            ttk.Style().configure("Accent.TButton", font=("Helvetica", 10, "bold"))
            self._btn_export.configure(style="Accent.TButton")
        except Exception:
            pass

        # ── Panel PDF ──────────────────────────────────────────────────────
        f_pdf = ttk.LabelFrame(f_exp, text="Exportar PDF", padding="5")
        f_pdf.pack(fill="x", pady=(5, 0))

        f_route = ttk.Frame(f_pdf)
        f_route.pack(fill="x", pady=2)
        ttk.Label(f_route, text="Mapas de ruta:", font=("Arial", 8)).pack(
            side="left"
        )
        ttk.Radiobutton(
            f_route, text="Consolidado",
            variable=self._pdf_route_mode, value="consolidated",
        ).pack(side="left", padx=5)
        ttk.Radiobutton(
            f_route, text="Por dia",
            variable=self._pdf_route_mode, value="daily",
        ).pack(side="left", padx=5)

        self._btn_export_pdf = ttk.Button(
            f_pdf,
            text="Exportar PDF",
            command=self._on_export_pdf,
            state=tk.DISABLED,
        )
        self._btn_export_pdf.pack(fill="x", pady=5, ipady=4)

    def _build_log_section(self, parent: ttk.Frame) -> None:
        # ── Barra de progreso (oculta por defecto) ────────────────────────
        self._progress_frame = ttk.Frame(parent)
        self._progress_frame.grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 0),
        )
        self._progress_frame.grid_columnconfigure(0, weight=1)

        self._progress_label = ttk.Label(
            self._progress_frame, text="", font=("Helvetica", 9),
        )
        self._progress_label.grid(row=0, column=0, sticky="w", padx=5)

        self._progress_pct = ttk.Label(
            self._progress_frame, text="0 %", font=("Helvetica", 9, "bold"),
        )
        self._progress_pct.grid(row=0, column=1, sticky="e", padx=5)

        self._progress_bar = ttk.Progressbar(
            self._progress_frame, orient="horizontal",
            mode="determinate", maximum=100,
        )
        self._progress_bar.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 4),
        )

        self._progress_frame.grid_remove()  # oculto por defecto

        # ── Log ───────────────────────────────────────────────────────────
        f_log = ttk.LabelFrame(
            parent, text="Registro de Actividad y Diagnóstico", padding="10"
        )
        f_log.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        f_log.grid_rowconfigure(0, weight=1)
        f_log.grid_columnconfigure(0, weight=1)

        self._log_widget = scrolledtext.ScrolledText(
            f_log,
            wrap=tk.WORD,
            height=8,
            state="disabled",
            font=GUI_LOG_FONT,
        )
        self._log_widget.grid(row=0, column=0, sticky="nsew")

    # ── Semáforo ──────────────────────────────────────────────────────────────

    def _show_progress(self) -> None:
        self._progress_bar["value"] = 0
        self._progress_label.config(text="Iniciando...")
        self._progress_pct.config(text="0 %")
        self._progress_frame.grid()

    def _hide_progress(self) -> None:
        self._progress_frame.grid_remove()

    def _set_status(self, color: str, text: str) -> None:
        # Actualizar el label de total como indicador general
        self._lbl_total.config(text=text)

    # ── Adjuntos PDF ──────────────────────────────────────────────────────────

    def _on_add_pdf(self) -> None:
        if self._is_busy:
            return
        path_str = filedialog.askopenfilename(
            title="Seleccionar PDF", filetypes=[("PDF", "*.pdf")]
        )
        if not path_str:
            return
        category = self._ask_category()
        if not category:
            return
        att = PdfAttachment(category=category, source_path=Path(path_str))
        self._pdf_list.append(att)
        self._tree_adj.insert("", "end", values=(att.category, att.filename))
        logger.info("Adjuntado: %s (%s)", att.filename, att.category)

    def _ask_category(self) -> Optional[str]:
        dialog = tk.Toplevel(self)
        dialog.title("Categoría")
        dialog.geometry("300x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        result: list[Optional[str]] = [None]

        ttk.Label(dialog, text="Tipo de documento:").pack(pady=10)
        combo = ttk.Combobox(
            dialog, values=list(PDF_CATEGORIES), state="readonly"
        )
        combo.pack(pady=5, padx=10, fill="x")
        combo.current(0)

        def _ok() -> None:
            result[0] = combo.get()
            dialog.destroy()

        ttk.Button(dialog, text="Aceptar", command=_ok).pack(pady=10)
        self.wait_window(dialog)
        return result[0]

    def _on_remove_pdf(self) -> None:
        selected = self._tree_adj.selection()
        if not selected:
            return
        for item in selected:
            values = self._tree_adj.item(item, "values")
            self._pdf_list = [
                p for p in self._pdf_list
                if not (p.filename == values[1] and p.category == values[0])
            ]
            self._tree_adj.delete(item)

    # ── Carga de archivo ──────────────────────────────────────────────────────

    def _on_load_file(self) -> None:
        if self._is_busy:
            return
        path_str = filedialog.askopenfilename(
            filetypes=[("Excel / CSV", "*.xlsx *.xls *.csv")]
        )
        if not path_str:
            return
        self._file_path.set(path_str)
        self._set_busy(True)
        self._set_status("yellow", "Analizando Archivo...")
        logger.info("Cargando: %s", Path(path_str).name)
        threading.Thread(
            target=self._thread_load,
            args=(Path(path_str),),
            daemon=True,
        ).start()

    def _on_remove_file(self) -> None:
        """Elimina el archivo seleccionado del listado."""
        if self._is_busy:
            return
        selected = self._tree_files.selection()
        if not selected:
            messagebox.showinfo(
                "Seleccionar",
                "Selecciona un archivo de la lista para eliminarlo.",
            )
            return

        iid = selected[0]
        entry = next(
            (e for e in self._loaded_files if e.get("iid") == iid), None
        )
        if entry is None:
            return

        confirm = messagebox.askyesno(
            "Confirmar Eliminación",
            f"¿Eliminar el archivo '{entry['name']}' de la lista?",
        )
        if not confirm:
            return

        self._loaded_files.remove(entry)
        self._tree_files.delete(iid)

        self._rebuild_accumulated()
        self._update_status_indicators()
        self._analysis_dirty = True
        self._df = None

        if not self._loaded_files:
            self._btn_analyze.config(state=tk.DISABLED)
            self._btn_edit_file.config(state=tk.DISABLED)
            self._btn_remove_file.config(state=tk.DISABLED)
            self._btn_aliases.config(state=tk.DISABLED)
            self._btn_case_data.config(state=tk.DISABLED)
            self._btn_export.config(state=tk.DISABLED)
            self._set_status("gray", "Total: 0 registros")
        else:
            self._btn_export.config(state=tk.DISABLED)

        logger.info("Archivo '%s' eliminado de la lista.", entry["name"])

    def _on_clear_files(self) -> None:
        """Limpia todos los archivos cargados y reinicia el estado."""
        if self._is_busy:
            return
        self._loaded_files.clear()
        self._accumulated_df = None
        self._df = None
        self._raw_df = None
        self._raw_sheets = None
        self._aliases.clear()
        self._file_counter = 0
        self._analysis_dirty = False

        # Limpiar treeview de archivos
        for item in self._tree_files.get_children():
            self._tree_files.delete(item)

        # Resetear indicadores
        self._update_status_indicators()
        self._btn_analyze.config(state=tk.DISABLED)
        self._btn_edit_file.config(state=tk.DISABLED)
        self._btn_remove_file.config(state=tk.DISABLED)
        self._btn_aliases.config(state=tk.DISABLED)
        self._btn_case_data.config(state=tk.DISABLED)
        self._btn_export.config(state=tk.DISABLED)
        self._btn_export_pdf.config(state=tk.DISABLED)
        self._report_base_dir = None
        self._last_ftp_url = ""
        self._set_status("gray", "Total: 0 registros")
        logger.info("Datos limpiados. Listo para nueva carga.")

    def _on_run_analysis(self) -> None:
        """Ejecuta el análisis (geocodificación) sobre los datos acumulados."""
        if self._is_busy or self._accumulated_df is None:
            return

        self._set_busy(True)
        self._set_status("yellow", "Analizando y geocodificando...")
        threading.Thread(
            target=self._thread_run_analysis,
            daemon=True,
        ).start()

    def _thread_run_analysis(self) -> None:
        """Geocodifica los datos acumulados y prepara para exportar."""
        try:
            df = self._accumulated_df.copy()
            df = self._geo_svc.geocode_by_cell_db(df)

            missing = self._geo_svc.count_missing_coords(df)
            if missing > 0 and "nombre_celda" in df.columns:
                self._work_queue.put(("ask_inference", (df, missing)))
                return

            self._df = df
            self._analysis_dirty = False
            stats = self._data_svc.compute_stats(df)
            self._work_queue.put(("load_ok", stats))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

    def _on_edit_file(self) -> None:
        """Re-abre el mapper para un archivo ya cargado."""
        selected = self._tree_files.selection()
        if not selected:
            messagebox.showinfo(
                "Seleccionar",
                "Selecciona un archivo de la lista para editar sus columnas.",
            )
            return

        iid = selected[0]
        entry = next(
            (e for e in self._loaded_files if e.get("iid") == iid), None
        )
        if entry is None or entry.get("raw_sheets") is None:
            messagebox.showwarning(
                "No disponible",
                "No se puede editar este archivo. Intenta eliminarlo y cargarlo de nuevo.",
            )
            return

        raw_sheets = entry["raw_sheets"]
        sheets_columns = {
            name: list(df.columns) for name, df in raw_sheets.items()
        }

        loaded_status = self._get_loaded_status_excluding(entry)

        dialog = SheetColumnMapperDialog(
            self, sheets_columns, loaded_status=loaded_status
        )
        self.wait_window(dialog)

        if not dialog.result:
            return

        # Re-procesar con nuevo mapeo
        self._set_busy(True)
        self._set_status("yellow", "Re-procesando...")
        threading.Thread(
            target=self._thread_reprocess_file,
            args=(entry, raw_sheets, dialog.result),
            daemon=True,
        ).start()

    def _get_loaded_status_excluding(self, exclude_entry: dict) -> dict[str, int]:
        """Calcula el estado de datos cargados excluyendo un archivo específico."""
        counts: dict[str, int] = {"Entrantes": 0, "Salientes": 0, "Datos": 0}
        for entry in self._loaded_files:
            if entry is exclude_entry:
                continue
            df = entry.get("processed_df")
            if df is None or COL_CALL_TYPE not in df.columns:
                continue
            upper = df[COL_CALL_TYPE].astype(str).str.upper()
            counts["Entrantes"] += int(upper.str.contains("ENTRANTE").sum())
            counts["Salientes"] += int(upper.str.contains("SALIENTE").sum())
            counts["Datos"] += int(upper.str.contains("DATO").sum())
        return counts

    def _thread_reprocess_file(
        self,
        entry: dict,
        sheets: dict[str, pd.DataFrame],
        sheet_configs: list[dict],
    ) -> None:
        """Re-procesa un archivo con nuevo mapeo."""
        try:
            df = self._data_svc.process_sheets(sheets, sheet_configs)
            types_found = self._detect_types_in_df(df)
            self._work_queue.put(("file_updated", {
                "entry": entry,
                "types": types_found,
                "rows": len(df),
                "sheet_configs": sheet_configs,
                "processed_df": df,
            }))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

    def _rebuild_accumulated(self) -> None:
        """Reconstruye el DataFrame acumulado desde todos los archivos cargados."""
        frames = [
            e["processed_df"]
            for e in self._loaded_files
            if e.get("processed_df") is not None
        ]
        if frames:
            self._accumulated_df = pd.concat(
                frames, ignore_index=True, sort=False
            )
            self._accumulated_df = self._accumulated_df.loc[
                :, ~self._accumulated_df.columns.duplicated()
            ]
        else:
            self._accumulated_df = None

    def _show_file_loaded_dialog(self, info: dict) -> str:
        """
        Muestra un diálogo claro tras cargar un archivo.

        Returns: 'add_more' o 'continue'
        """
        dialog = tk.Toplevel(self)
        dialog.title("Archivo Cargado")
        dialog.geometry("420x200")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        result: list[str] = ["continue"]

        types_str = ", ".join(info["types"])
        ttk.Label(
            dialog,
            text=f"Archivo: {info['name']}",
            font=("Arial", 10, "bold"),
        ).pack(pady=(15, 5))
        ttk.Label(
            dialog,
            text=f"Registros cargados: {info['rows']}   |   Tipo: {types_str}",
        ).pack(pady=(0, 15))

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=20, pady=5)

        def _add_more() -> None:
            result[0] = "add_more"
            dialog.destroy()

        def _continue() -> None:
            result[0] = "continue"
            dialog.destroy()

        ttk.Button(
            btn_frame,
            text="Subir Otro Archivo",
            command=_add_more,
        ).pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=5)

        ttk.Button(
            btn_frame,
            text="Continuar al Análisis",
            command=_continue,
        ).pack(side="right", expand=True, fill="x", padx=(5, 0), ipady=5)

        dialog.protocol("WM_DELETE_WINDOW", _continue)
        self.wait_window(dialog)
        return result[0]

    def _update_status_indicators(self) -> None:
        """Actualiza los indicadores visuales de tipos de datos cargados."""
        counts = {"entrante": 0, "saliente": 0, "datos": 0}

        if self._accumulated_df is not None and COL_CALL_TYPE in self._accumulated_df.columns:
            type_col = self._accumulated_df[COL_CALL_TYPE].astype(str).str.upper()
            counts["entrante"] = int(type_col.str.contains("ENTRANTE").sum())
            counts["saliente"] = int(type_col.str.contains("SALIENTE").sum())
            counts["datos"] = int(type_col.str.contains("DATO").sum())

        total = sum(counts.values())
        labels_map = {"entrante": "Entrantes", "saliente": "Salientes", "datos": "Datos"}

        for tipo, info in self._status_indicators.items():
            count = counts.get(tipo, 0)
            color = "#28a745" if count > 0 else "#6c757d"
            info["canvas"].itemconfig(info["light"], fill=color, outline=color)
            info["label"].config(text=f"{labels_map[tipo]}: {count}")
            info["count"] = count

        self._lbl_total.config(text=f"Total: {total} registros")
        self._lbl_files_count.config(text=f"Archivos: {len(self._loaded_files)}")

    def _add_file_to_list(self, filename: str, types: list[str], rows: int) -> str:
        """Agrega un archivo al treeview de archivos cargados. Devuelve el iid."""
        self._file_counter += 1
        iid = f"file_{self._file_counter}"
        tipos_str = ", ".join(types) if types else "Genérica"
        self._tree_files.insert(
            "", "end", iid=iid, values=(filename, tipos_str, rows)
        )
        return iid

    def _thread_load(self, path: Path) -> None:
        try:
            # Intentar carga multi-hoja primero
            sheets, error = self._data_svc.load_sheets_raw(path)
            if sheets is not None and len(sheets) >= 1:
                # Siempre usar el flujo por hoja (incluso con 1 sola hoja)
                # para que el usuario elija el tipo (Entrantes/Salientes/Datos)
                self._raw_sheets = sheets
                self._work_queue.put(("ask_sheet_mapping", sheets))
                return

            # Fallback: carga clásica (CSV u otros)
            df_raw, error = self._data_svc.load_raw(path)
            if df_raw is None:
                self._work_queue.put(("error", error or "Error desconocido"))
                return
            self._raw_df = df_raw
            self._work_queue.put(("ask_mapping", df_raw))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

    def _continue_with_mapping(self, df_raw: pd.DataFrame) -> None:
        dialog = ColumnMapperDialog(self, list(df_raw.columns))
        self.wait_window(dialog)

        if not dialog.result:
            logger.warning("Carga cancelada por el usuario.")
            self._set_busy(False)
            self._set_status("gray", "Carga Cancelada")
            return

        self._set_status("yellow", "Limpiando Datos...")
        threading.Thread(
            target=self._thread_process,
            args=(df_raw, dialog.result),
            daemon=True,
        ).start()

    def _continue_with_sheet_mapping(
        self, sheets: dict[str, pd.DataFrame]
    ) -> None:
        """Abre el diálogo de mapeo por hoja y procesa el resultado."""
        sheets_columns = {
            name: list(df.columns) for name, df in sheets.items()
        }

        # Pasar estado de datos ya cargados al diálogo
        loaded_status: dict[str, int] = {}
        if self._accumulated_df is not None and COL_CALL_TYPE in self._accumulated_df.columns:
            upper = self._accumulated_df[COL_CALL_TYPE].astype(str).str.upper()
            loaded_status["Entrantes"] = int(upper.str.contains("ENTRANTE").sum())
            loaded_status["Salientes"] = int(upper.str.contains("SALIENTE").sum())
            loaded_status["Datos"] = int(upper.str.contains("DATO").sum())

        dialog = SheetColumnMapperDialog(
            self, sheets_columns, loaded_status=loaded_status
        )
        self.wait_window(dialog)

        if not dialog.result:
            logger.warning("Carga cancelada por el usuario.")
            self._set_busy(False)
            self._set_status("gray", "Carga Cancelada")
            return

        self._set_status("yellow", "Limpiando Datos...")
        threading.Thread(
            target=self._thread_process_sheets,
            args=(sheets, dialog.result),
            daemon=True,
        ).start()

    def _thread_process_sheets(
        self,
        sheets: dict[str, pd.DataFrame],
        sheet_configs: list[dict],
    ) -> None:
        """Procesa múltiples hojas con mapeos individuales y acumula."""
        try:
            logger.info(
                "Procesando %d hojas con mapeo individual...", len(sheet_configs)
            )
            df = self._data_svc.process_sheets(sheets, sheet_configs)
            types_found = self._detect_types_in_df(df)
            filename = Path(self._file_path.get()).name

            self._work_queue.put((
                "file_added",
                {
                    "name": filename,
                    "path": Path(self._file_path.get()),
                    "types": types_found,
                    "rows": len(df),
                    "raw_sheets": sheets,
                    "sheet_configs": sheet_configs,
                    "processed_df": df,
                },
            ))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

    def _thread_process(
        self, df_raw: pd.DataFrame, mapping: dict[str, str]
    ) -> None:
        """Procesa un archivo con mapeo simple y acumula."""
        try:
            logger.info("Ejecutando limpieza y normalización...")
            df = self._data_svc.process(df_raw, mapping)
            types_found = self._detect_types_in_df(df)
            filename = Path(self._file_path.get()).name

            self._work_queue.put((
                "file_added",
                {
                    "name": filename,
                    "path": Path(self._file_path.get()),
                    "types": types_found,
                    "rows": len(df),
                    "raw_sheets": {filename: df_raw},
                    "sheet_configs": [{"mapping": mapping}],
                    "processed_df": df,
                },
            ))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

    @staticmethod
    def _detect_types_in_df(df: pd.DataFrame) -> list[str]:
        """Detecta qué tipos de datos contiene un DataFrame procesado."""
        types: list[str] = []
        if COL_CALL_TYPE not in df.columns:
            return ["Genérica"]
        upper = df[COL_CALL_TYPE].astype(str).str.upper()
        if upper.str.contains("ENTRANTE").any():
            types.append("Entrantes")
        if upper.str.contains("SALIENTE").any():
            types.append("Salientes")
        if upper.str.contains("DATO").any():
            types.append("Datos")
        return types or ["Genérica"]

    def _run_inference(self, df: pd.DataFrame) -> None:
        threading.Thread(
            target=self._thread_inference, args=(df,), daemon=True
        ).start()

    def _thread_inference(self, df: pd.DataFrame) -> None:
        try:
            self._set_status("yellow", "Infiriendo Ubicaciones...")
            logger.info("Infiriendo ubicación por nombre de municipio...")
            df = self._geo_svc.geocode_by_municipality_name(df)
            self._df = df
            stats = self._data_svc.compute_stats(df)
            self._work_queue.put(("load_ok", stats))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

    # ── Alias / Datos del caso ────────────────────────────────────────────────

    def _on_assign_aliases(self) -> None:
        if self._df is None:
            return
        numbers = sorted(
            set(
                list(self._df["originador"].dropna().astype(str).unique())
                + list(self._df["receptor"].dropna().astype(str).unique())
            )
        )
        self._open_alias_editor(numbers)

    def _open_alias_editor(self, numbers: list[str]) -> None:
        w = tk.Toplevel(self)
        w.title(f"Asignar Nombres ({len(numbers)} números)")
        w.geometry("600x700")
        w.transient(self)
        w.grab_set()

        ttk.Label(w, text="Buscar:").pack(side="top", anchor="w", padx=10, pady=(10, 0))
        search_var = tk.StringVar()
        ttk.Entry(w, textvariable=search_var).pack(fill="x", padx=10)

        container = ttk.Frame(w)
        container.pack(fill="both", expand=True, padx=10, pady=5)
        canvas = tk.Canvas(container, bg="#f9f9f9")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        frame_list = ttk.Frame(canvas)
        frame_list.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=frame_list, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        entry_vars: dict[str, tk.StringVar] = {}

        def render(filter_text: str = "") -> None:
            for child in frame_list.winfo_children():
                child.destroy()
            entry_vars.clear()
            for idx, num in enumerate(numbers):
                current_alias = self._aliases.get(num, "")
                if filter_text and (
                    filter_text.lower() not in num.lower()
                    and filter_text.lower() not in current_alias.lower()
                ):
                    continue
                bg = "#ffffff" if idx % 2 == 0 else "#f0f0f0"
                row_frame = tk.Frame(frame_list, bg=bg, pady=2)
                row_frame.pack(fill="x")
                tk.Label(
                    row_frame, text=num, width=20, anchor="w", bg=bg,
                    font=("Arial", 10, "bold"),
                ).pack(side="left", padx=10)
                var = tk.StringVar(value=current_alias)
                ttk.Entry(row_frame, textvariable=var, width=40).pack(
                    side="left", fill="x", expand=True, padx=10
                )
                entry_vars[num] = var

        render()
        search_var.trace("w", lambda *_: render(search_var.get()))

        def _save() -> None:
            for num, var in entry_vars.items():
                val = var.get().strip()
                if val:
                    self._aliases[num] = val
                elif num in self._aliases:
                    del self._aliases[num]
            logger.info("Alias actualizados: %d.", len(self._aliases))
            messagebox.showinfo("Guardado", "Nombres asignados correctamente.")
            w.destroy()

        ttk.Button(w, text="Guardar Cambios", command=_save).pack(
            fill="x", padx=10, pady=10, ipady=5
        )

    def _on_edit_case_data(self) -> None:
        w = tk.Toplevel(self)
        w.title("Datos del Caso")
        w.geometry("500x520")
        w.transient(self)
        w.grab_set()

        ttk.Label(w, text="Información del Caso", font=("Arial", 12, "bold")).pack(
            pady=(15, 5)
        )

        canvas = tk.Canvas(w, bg="white", height=320)
        sb = ttk.Scrollbar(w, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw", width=460)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="top", fill="both", expand=True, padx=10)
        sb.pack(side="right", fill="y")

        row_widgets: dict[int, tuple[tk.StringVar, tk.StringVar]] = {}
        _row_counter = [0]  # contador monotónico para IDs únicos

        def add_row(key: str = "", val: str = "") -> None:
            _row_counter[0] += 1
            row_id = _row_counter[0]
            f_row = ttk.Frame(inner)
            f_row.pack(fill="x", pady=2)
            ttk.Button(
                f_row, text="X", width=3,
                command=lambda rid=row_id, fr=f_row: [
                    row_widgets.pop(rid, None), fr.destroy()
                ],
            ).pack(side="left", padx=(0, 5))
            k_var = tk.StringVar(value=key)
            v_var = tk.StringVar(value=val)
            ttk.Entry(f_row, textvariable=k_var, width=18, font=("Arial", 9, "bold")).pack(
                side="left"
            )
            ttk.Label(f_row, text=":").pack(side="left")
            ttk.Entry(f_row, textvariable=v_var).pack(
                side="left", fill="x", expand=True, padx=5
            )
            row_widgets[row_id] = (k_var, v_var)

        # Mostrar solo los campos que el usuario tiene guardados,
        # respetando su orden y sin forzar los por defecto.
        existing = self._case_metadata.to_dict()
        for k, v in existing.items():
            add_row(k, v)

        actions = ttk.Frame(w)
        actions.pack(fill="x", padx=10, pady=5)
        ttk.Button(actions, text="+ Agregar Campo", command=lambda: add_row()).pack(
            fill="x", pady=3
        )

        def _save() -> None:
            data = {}
            for k_var, v_var in row_widgets.values():
                k = k_var.get().strip()
                v = v_var.get().strip()
                if k:
                    data[k] = v
            self._case_metadata = CaseMetadata(fields=data)
            logger.info("Datos del caso actualizados.")
            w.destroy()

        ttk.Button(actions, text="Guardar y Cerrar", command=_save).pack(
            fill="x", pady=5, ipady=5
        )

    # ── Exportar ──────────────────────────────────────────────────────────────

    def _on_export(self) -> None:
        if self._is_busy or self._df is None:
            return

        config = ReportConfig(
            report_name=self._report_name.get().strip() or "Informe_Llamadas",
            include_letterhead=self._include_logo.get(),
            upload_ftp=self._upload_ftp.get(),
            aliases=dict(self._aliases),
            case_metadata=CaseMetadata(fields=self._case_metadata.to_dict()),
            pdf_attachments=list(self._pdf_list),
        )

        self._set_busy(True)
        self._btn_export.config(text="Trabajando...")
        self._set_status("yellow", "Generando Informe...")
        self._show_progress()
        threading.Thread(
            target=self._thread_export, args=(config,), daemon=True
        ).start()

    def _thread_export(self, config: ReportConfig) -> None:
        try:
            def _progress_cb(pct: int, text: str) -> None:
                self._work_queue.put(("progress", (pct, text)))

            logger.info("Generando informe: %s", config.safe_name)
            base_dir = self._report_gen.generate(
                self._df, config, progress_callback=_progress_cb,
            )
            self._report_base_dir = base_dir

            if config.upload_ftp:
                self._work_queue.put(("status", "Subiendo a FTP..."))
                url = self._upload_svc.upload(base_dir, config.safe_name)
                self._work_queue.put(("ftp_ok", url))
            else:
                report_path = base_dir / "reports" / "informe_llamadas.html"
                self._work_queue.put(("local_ok", str(report_path)))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

    # ── Exportar PDF ───────────────────────────────────────────────────────

    def _on_export_pdf(self) -> None:
        if self._is_busy or self._df is None or self._report_base_dir is None:
            return

        config = ReportConfig(
            report_name=self._report_name.get().strip() or "Informe_Llamadas",
            include_letterhead=self._include_logo.get(),
            upload_ftp=False,
            aliases=dict(self._aliases),
            case_metadata=CaseMetadata(fields=self._case_metadata.to_dict()),
            pdf_attachments=list(self._pdf_list),
        )
        pdf_config = PdfExportConfig(
            route_map_mode=(
                RouteMapMode.DAILY
                if self._pdf_route_mode.get() == "daily"
                else RouteMapMode.CONSOLIDATED
            ),
            ftp_url=self._last_ftp_url,
        )

        self._set_busy(True)
        self._btn_export_pdf.config(text="Generando PDF...")
        self._set_status("yellow", "Generando PDF...")
        self._show_progress()
        threading.Thread(
            target=self._thread_export_pdf,
            args=(config, pdf_config),
            daemon=True,
        ).start()

    def _thread_export_pdf(
        self, config: ReportConfig, pdf_config: PdfExportConfig,
    ) -> None:
        try:
            from config.constants import (
                COL_CALL_TYPE as _COL_CT,
                PDF_MAP_DIR_NAME,
            )
            from reports.builders.pdf_builder import PdfReportBuilder
            from reports.builders.static_map_builder import (
                StaticLocationMapBuilder,
                StaticRouteMapBuilder,
            )
            from reports.integrity import write_sha256_companion

            def _progress_cb(pct: int, text: str) -> None:
                self._work_queue.put(("progress", (pct, text)))

            base_dir = self._report_base_dir
            df = self._df

            # 1. Separar llamadas y datos
            _progress_cb(5, "Separando datos...")
            mask_data = df[_COL_CT].astype(str).str.upper().str.contains("DATO")
            df_calls = df[~mask_data].copy()
            df_data = df[mask_data].copy()

            # 2. Crear directorio de mapas estáticos
            _progress_cb(8, "Preparando directorios...")
            static_maps_dir = base_dir / PDF_MAP_DIR_NAME
            static_maps_dir.mkdir(parents=True, exist_ok=True)

            # 3. Generar mapas estáticos
            _progress_cb(15, "Generando mapa de ubicaciones...")
            self._work_queue.put(("status", "Generando mapas para PDF..."))
            try:
                StaticLocationMapBuilder.build(
                    df_calls, static_maps_dir / "mapa_ubicaciones.png",
                    aliases=config.aliases,
                )
            except Exception as exc:
                logger.warning("No se pudo generar mapa de ubicaciones: %s", exc)

            try:
                if pdf_config.route_map_mode == RouteMapMode.DAILY:
                    def _daily_progress(idx: int, total: int, date: str) -> None:
                        pct = 20 + int(30 * idx / max(total, 1))
                        _progress_cb(pct, f"Generando mapa día {idx} de {total}...")

                    StaticRouteMapBuilder.build_daily(
                        df_data, static_maps_dir, aliases=config.aliases,
                        progress_callback=_daily_progress,
                    )
                else:
                    _progress_cb(35, "Generando mapa de ruta consolidada...")
                    StaticRouteMapBuilder.build_consolidated(
                        df_data, static_maps_dir / "ruta_consolidada.png",
                        aliases=config.aliases,
                    )
            except Exception as exc:
                logger.warning("No se pudo generar mapa de ruta: %s", exc)

            # 4. Construir PDF
            self._work_queue.put(("status", "Construyendo PDF..."))
            pdf_path = base_dir / "reports" / "informe_llamadas.pdf"

            builder = PdfReportBuilder()
            builder.build(
                df=df,
                output_path=pdf_path,
                report_config=config,
                pdf_config=pdf_config,
                base_dir=base_dir,
                geocoding_service=self._geo_svc,
                progress_callback=_progress_cb,
            )

            # 5. SHA-256
            _progress_cb(95, "Calculando SHA-256...")
            self._work_queue.put(("status", "Calculando SHA-256..."))
            write_sha256_companion(pdf_path)

            _progress_cb(100, "PDF completado")
            logger.info("PDF generado: %s", pdf_path)
            self._work_queue.put(("pdf_ok", str(pdf_path)))

        except Exception as exc:
            logger.exception("Error generando PDF")
            self._work_queue.put(("error", f"Error PDF: {exc}"))

    # ── Subir PDF al FTP ───────────────────────────────────────────────────

    def _upload_pdf_to_ftp(self, pdf_path: Path, sha_path: Path) -> None:
        """Sube el PDF y su hash SHA-256 al FTP en la misma carpeta del informe."""
        self._set_busy(True)
        self._set_status("yellow", "Subiendo PDF al FTP...")
        self._show_progress()
        threading.Thread(
            target=self._thread_upload_pdf,
            args=(pdf_path, sha_path),
            daemon=True,
        ).start()

    def _thread_upload_pdf(self, pdf_path: Path, sha_path: Path) -> None:
        try:
            # Extraer remote_folder del _last_ftp_url
            # URL: https://host/<safe_name>/reports/informe_llamadas.html
            # remote_folder para PDFs: <safe_name>/reports
            url_parts = self._last_ftp_url.replace("https://", "").split("/")
            # url_parts = [host, safe_name, "reports", "informe_llamadas.html"]
            remote_folder = "/".join(url_parts[1:-1])  # safe_name/reports

            self._work_queue.put(("progress", (30, "Subiendo PDF...")))
            pdf_url = self._upload_svc.upload_file(pdf_path, remote_folder)

            self._work_queue.put(("progress", (70, "Subiendo SHA-256...")))
            if sha_path.exists():
                self._upload_svc.upload_file(sha_path, remote_folder)

            self._work_queue.put(("progress", (100, "PDF subido")))
            self._work_queue.put(("pdf_ftp_ok", pdf_url))

        except Exception as exc:
            logger.exception("Error subiendo PDF al FTP")
            self._work_queue.put(("error", f"Error subiendo PDF: {exc}"))

    # ── Cola de mensajes (Thread-safe UI updates) ─────────────────────────────

    def _poll_queue(self) -> None:
        try:
            while True:
                msg_type, payload = self._work_queue.get_nowait()
                self._handle_message(msg_type, payload)
        except queue.Empty:
            pass
        finally:
            self.after(QUEUE_POLL_MS, self._poll_queue)

    def _handle_message(self, msg_type: str, payload: object) -> None:
        if msg_type == "ask_mapping":
            self._continue_with_mapping(payload)

        elif msg_type == "ask_sheet_mapping":
            self._continue_with_sheet_mapping(payload)

        elif msg_type == "file_added":
            info = payload
            iid = self._add_file_to_list(
                info["name"], info["types"], info["rows"]
            )
            # Guardar entrada completa con datos crudos para re-edición
            info["iid"] = iid
            self._loaded_files.append(info)
            self._rebuild_accumulated()
            self._update_status_indicators()
            self._set_busy(False)
            self._btn_analyze.config(state=tk.NORMAL)
            self._btn_edit_file.config(state=tk.NORMAL)
            self._btn_remove_file.config(state=tk.NORMAL)
            self._analysis_dirty = True
            types_str = ", ".join(info["types"])
            logger.info(
                "Archivo '%s' agregado: %d registros (%s).",
                info["name"], info["rows"], types_str,
            )

            # Diálogo claro con botones descriptivos
            action = self._show_file_loaded_dialog(info)
            if action == "add_more":
                self._on_load_file()
            else:
                self._on_run_analysis()

        elif msg_type == "file_updated":
            info = payload
            entry = info["entry"]
            entry["types"] = info["types"]
            entry["rows"] = info["rows"]
            entry["sheet_configs"] = info["sheet_configs"]
            entry["processed_df"] = info["processed_df"]

            # Actualizar treeview
            iid = entry.get("iid")
            if iid:
                tipos_str = ", ".join(info["types"])
                self._tree_files.item(
                    iid, values=(entry["name"], tipos_str, info["rows"])
                )

            self._rebuild_accumulated()
            self._update_status_indicators()
            self._set_busy(False)
            self._analysis_dirty = True
            self._df = None
            self._btn_analyze.config(state=tk.NORMAL)
            self._btn_export.config(state=tk.DISABLED)
            self._btn_export_pdf.config(state=tk.DISABLED)
            self._report_base_dir = None
            logger.info(
                "Archivo '%s' re-mapeado: %d registros.", entry["name"], info["rows"]
            )
            messagebox.showinfo(
                "Archivo Actualizado",
                f"'{entry['name']}' re-procesado con {info['rows']} registros.\n\n"
                "Presiona 'Realizar Análisis' para actualizar el informe.",
            )

        elif msg_type == "ask_inference":
            df, missing_count = payload
            answer = messagebox.askyesno(
                "Ubicación Incompleta",
                f"Se detectaron {missing_count} registros sin ubicación exacta.\n\n"
                "¿Desea inferir la ubicación desde el nombre de la antena?\n"
                "(Ej: 'ANT.BARBOSA' → coordenadas del centro de Barbosa)",
            )
            if answer:
                logger.info("Usuario aceptó inferencia por municipio.")
                self._run_inference(df)
            else:
                self._df = df
                stats = self._data_svc.compute_stats(df)
                self._work_queue.put(("load_ok", stats))

        elif msg_type == "load_ok":
            stats: CallStats = payload
            self._analysis_dirty = False
            self._set_busy(False)
            self._set_status("green", "Datos Listos")
            self._btn_analyze.config(state=tk.DISABLED)
            self._enable_data_buttons()
            self._update_status_indicators()
            logger.info("Análisis finalizado. %d registros.", stats.total)
            msg = (
                f"Análisis listo.\n\n"
                f"Total: {stats.total}\n"
                f"Entrantes: {stats.incoming}\n"
                f"Salientes: {stats.outgoing}\n"
                f"Datos Internet: {stats.data_records}"
            )
            messagebox.showinfo("Análisis Completado", msg)

        elif msg_type == "error":
            logger.error("Error: %s", payload)
            messagebox.showerror("Error", str(payload))
            self._set_busy(False)
            self._set_status("red", "Error")
            self._hide_progress()
            self._btn_export.config(text="Generar y Exportar Informe")
            self._btn_export_pdf.config(text="Exportar PDF")

        elif msg_type == "status":
            self._set_status("yellow", str(payload))

        elif msg_type == "progress":
            pct, text = payload
            self._progress_bar["value"] = pct
            self._progress_label.config(text=text)
            self._progress_pct.config(text=f"{pct} %")

        elif msg_type == "local_ok":
            self._set_busy(False)
            self._btn_export.config(text="Generar y Exportar Informe")
            self._set_status("green", "Informe Generado")
            self._hide_progress()
            self._btn_export_pdf.config(state=tk.NORMAL)
            if messagebox.askyesno("Éxito", f"Guardado en:\n{payload}\n\n¿Abrir?"):
                try:
                    os.startfile(str(payload))  # Windows
                except Exception:
                    pass

        elif msg_type == "ftp_ok":
            self._set_busy(False)
            self._btn_export.config(text="Generar y Exportar Informe")
            self._set_status("green", "Subido a Web")
            self._hide_progress()
            self._last_ftp_url = str(payload)
            self._btn_export_pdf.config(state=tk.NORMAL)
            self._show_url(str(payload))

        elif msg_type == "pdf_ok":
            self._set_busy(False)
            self._btn_export_pdf.config(text="Exportar PDF")
            self._set_status("green", "PDF Generado")
            self._hide_progress()
            pdf_path = str(payload)
            sha_path = pdf_path + ".sha256"

            # Ofrecer subir al FTP si ya se subió el informe HTML
            if self._last_ftp_url:
                msg = (
                    f"PDF generado exitosamente:\n{pdf_path}\n\n"
                    f"Hash SHA-256:\n{sha_path}\n\n"
                    f"¿Desea subir el PDF al servidor FTP?"
                )
                if messagebox.askyesno("PDF Exportado", msg):
                    self._upload_pdf_to_ftp(Path(pdf_path), Path(sha_path))
                    return
                # Si no quiere subir al FTP, ofrecer abrir localmente
                if messagebox.askyesno("Abrir PDF", "¿Desea abrir el PDF?"):
                    try:
                        os.startfile(pdf_path)
                    except Exception:
                        pass
            else:
                msg = (
                    f"PDF generado exitosamente:\n{pdf_path}\n\n"
                    f"Hash SHA-256:\n{sha_path}\n\n"
                    f"¿Abrir el PDF?"
                )
                if messagebox.askyesno("PDF Exportado", msg):
                    try:
                        os.startfile(pdf_path)
                    except Exception:
                        pass

        elif msg_type == "pdf_ftp_ok":
            self._set_busy(False)
            self._set_status("green", "PDF subido al FTP")
            self._hide_progress()
            pdf_url = str(payload)
            self._show_url(pdf_url)

    # ── Helpers de estado ─────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._is_busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in (
            self._btn_load,
            self._btn_add_pdf,
            self._btn_del_pdf,
            self._btn_export,
            self._btn_export_pdf,
            self._btn_clear_files,
            self._btn_edit_file,
        ):
            btn.config(state=state)
        if busy:
            self._btn_analyze.config(state=tk.DISABLED)
        elif self._accumulated_df is not None and self._analysis_dirty:
            self._btn_analyze.config(state=tk.NORMAL)
        if not busy and self._loaded_files:
            self._btn_edit_file.config(state=tk.NORMAL)
        if not busy and self._df is not None:
            self._enable_data_buttons()
        # El botón PDF solo se habilita si ya se generó el informe HTML
        if not busy and self._report_base_dir is None:
            self._btn_export_pdf.config(state=tk.DISABLED)

    def _enable_data_buttons(self) -> None:
        self._btn_aliases.config(state=tk.NORMAL)
        self._btn_case_data.config(state=tk.NORMAL)
        self._btn_export.config(state=tk.NORMAL)

    def _show_url(self, url: str) -> None:
        w = tk.Toplevel(self)
        w.title("URL del Informe")
        w.geometry("600x100")
        entry = ttk.Entry(w, width=75)
        entry.pack(pady=15, padx=10)
        entry.insert(0, url)
        entry.config(state="readonly")
        ttk.Button(
            w,
            text="Copiar",
            command=lambda: (self.clipboard_clear(), self.clipboard_append(url)),
        ).pack()
