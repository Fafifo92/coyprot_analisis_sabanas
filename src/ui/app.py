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
    DEFAULT_CASE_FIELDS,
    GUI_GEOMETRY,
    GUI_LOG_FONT,
    GUI_MIN_SIZE,
    GUI_THEME,
    PDF_CATEGORIES,
    QUEUE_POLL_MS,
)
from config.settings import settings
from core.models import CallStats, CaseMetadata, PdfAttachment, ReportConfig
from reports.report_generator import ReportGenerator
from services.data_processing_service import DataProcessingService
from services.geocoding_service import GeocodingService
from services.upload_service import UploadService
from ui.dialogs.column_mapper import ColumnMapperDialog
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
        self._work_queue: queue.Queue = queue.Queue()
        self._is_busy = False

        # ── Variables Tkinter ─────────────────────────────────────────────────
        self._file_path = tk.StringVar()
        self._report_name = tk.StringVar(value="Informe_Llamadas")
        self._include_logo = tk.BooleanVar(value=True)
        self._upload_ftp = tk.BooleanVar(value=False)
        self._aliases: dict[str, str] = {}
        self._case_metadata = CaseMetadata.with_defaults()
        self._pdf_list: list[PdfAttachment] = []

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
        main = ttk.Frame(self, padding="15")
        main.pack(expand=True, fill=tk.BOTH)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(3, weight=1)

        self._build_file_section(main)
        self._build_attachments_section(main)
        self._build_options_and_export(main)
        self._build_log_section(main)

    def _build_file_section(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=1)

        # Carga de archivo
        f_load = ttk.LabelFrame(top, text="Archivo Principal", padding="15")
        f_load.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        f_load.grid_columnconfigure(1, weight=1)

        ttk.Label(f_load, text="Excel/CSV:").grid(row=0, column=0, padx=5, sticky="w")
        ttk.Entry(
            f_load, textvariable=self._file_path, width=50, state="readonly"
        ).grid(row=0, column=1, padx=10, sticky="ew")
        self._btn_load = ttk.Button(
            f_load, text="Seleccionar Archivo", command=self._on_load_file
        )
        self._btn_load.grid(row=0, column=2, padx=5)

        # Semáforo de estado
        f_status = ttk.LabelFrame(top, text="Estado de Datos", padding="10")
        f_status.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self._canvas_status = tk.Canvas(
            f_status, width=30, height=30, highlightthickness=0
        )
        self._canvas_status.pack(side="left", padx=5)
        self._status_light = self._canvas_status.create_oval(
            5, 5, 25, 25, fill="gray", outline="gray"
        )
        self._lbl_status = ttk.Label(
            f_status, text="Esperando...", font=("Arial", 9, "bold")
        )
        self._lbl_status.pack(side="left", padx=5)

    def _build_attachments_section(self, parent: ttk.Frame) -> None:
        f_adj = ttk.LabelFrame(parent, text="Adjuntos (PDF)", padding="10")
        f_adj.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        f_adj.grid_columnconfigure(0, weight=1)

        self._tree_adj = ttk.Treeview(
            f_adj, columns=("cat", "arch"), show="headings", height=4
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

    def _build_log_section(self, parent: ttk.Frame) -> None:
        f_log = ttk.LabelFrame(
            parent, text="Registro de Actividad y Diagnóstico", padding="10"
        )
        f_log.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        f_log.grid_rowconfigure(0, weight=1)
        f_log.grid_columnconfigure(0, weight=1)

        self._log_widget = scrolledtext.ScrolledText(
            f_log,
            wrap=tk.WORD,
            height=10,
            state="disabled",
            font=GUI_LOG_FONT,
        )
        self._log_widget.grid(row=0, column=0, sticky="nsew")

    # ── Semáforo ──────────────────────────────────────────────────────────────

    def _set_status(self, color: str, text: str) -> None:
        fill = _SEMAPHORE_COLORS.get(color, "#6c757d")
        self._canvas_status.itemconfig(self._status_light, fill=fill, outline=fill)
        self._lbl_status.config(text=text)

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

    def _thread_load(self, path: Path) -> None:
        try:
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

    def _thread_process(
        self, df_raw: pd.DataFrame, mapping: dict[str, str]
    ) -> None:
        try:
            logger.info("Ejecutando limpieza y normalización...")
            df = self._data_svc.process(df_raw, mapping)

            # Geocodificación por DB de celdas
            df = self._geo_svc.geocode_by_cell_db(df)

            missing = self._geo_svc.count_missing_coords(df)
            if missing > 0 and "nombre_celda" in df.columns:
                self._work_queue.put(("ask_inference", (df, missing)))
                return

            self._df = df
            stats = self._data_svc.compute_stats(df)
            self._work_queue.put(("load_ok", stats))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

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

        def add_row(key: str = "", val: str = "") -> None:
            row_id = len(row_widgets) + 1
            f_row = ttk.Frame(inner)
            f_row.pack(fill="x", pady=2)
            ttk.Button(
                f_row, text="X", width=3,
                command=lambda: [row_widgets.pop(row_id, None), f_row.destroy()],
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

        existing = self._case_metadata.to_dict()
        for field in DEFAULT_CASE_FIELDS:
            add_row(field, existing.get(field, ""))
        for k, v in existing.items():
            if k not in DEFAULT_CASE_FIELDS:
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
        threading.Thread(
            target=self._thread_export, args=(config,), daemon=True
        ).start()

    def _thread_export(self, config: ReportConfig) -> None:
        try:
            logger.info("Generando informe: %s", config.safe_name)
            base_dir = self._report_gen.generate(self._df, config)

            if config.upload_ftp:
                self._work_queue.put(("status", "Subiendo a FTP..."))
                url = self._upload_svc.upload(base_dir, config.safe_name)
                self._work_queue.put(("ftp_ok", url))
            else:
                report_path = base_dir / "reports" / "informe_llamadas.html"
                self._work_queue.put(("local_ok", str(report_path)))
        except Exception as exc:
            self._work_queue.put(("error", str(exc)))

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
            self._set_busy(False)
            self._set_status("green", "Datos Listos")
            self._enable_data_buttons()
            logger.info("Carga finalizada. %d registros.", stats.total)
            msg = (
                f"Datos listos.\n\n"
                f"Total: {stats.total}\n"
                f"Entrantes: {stats.incoming}\n"
                f"Salientes: {stats.outgoing}\n"
                f"Datos Internet: {stats.data_records}"
            )
            messagebox.showinfo("Carga Exitosa", msg)

        elif msg_type == "error":
            logger.error("Error: %s", payload)
            messagebox.showerror("Error", str(payload))
            self._set_busy(False)
            self._set_status("red", "Error")
            self._btn_export.config(text="Generar y Exportar Informe")

        elif msg_type == "status":
            self._btn_export.config(text=str(payload))
            self._set_status("yellow", str(payload))

        elif msg_type == "local_ok":
            self._set_busy(False)
            self._btn_export.config(text="Generar y Exportar Informe")
            self._set_status("green", "Informe Generado")
            if messagebox.askyesno("Éxito", f"Guardado en:\n{payload}\n\n¿Abrir?"):
                try:
                    os.startfile(str(payload))  # Windows
                except Exception:
                    pass

        elif msg_type == "ftp_ok":
            self._set_busy(False)
            self._btn_export.config(text="Generar y Exportar Informe")
            self._set_status("green", "Subido a Web")
            self._show_url(str(payload))

    # ── Helpers de estado ─────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._is_busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in (self._btn_load, self._btn_add_pdf, self._btn_del_pdf, self._btn_export):
            btn.config(state=state)
        if not busy and self._df is not None:
            self._enable_data_buttons()

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
