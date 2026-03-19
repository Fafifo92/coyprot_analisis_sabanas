"""
Diálogo de mapeo de columnas por hoja.

Permite al usuario asignar un tipo (Entrantes, Salientes, Datos, Genérica, Ignorar)
a cada hoja del Excel y mapear las columnas de cada hoja individualmente.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from config.constants import (
    COLUMN_MAPPING_FIELDS,
    COL_CALL_TYPE,
    COL_RECEIVER,
    REQUIRED_MAPPING_FIELDS,
    REQUIRED_MAPPING_FIELDS_DATA,
    SHEET_DETECT_KEYWORDS,
    SHEET_TYPE_DATA,
    SHEET_TYPE_GENERIC,
    SHEET_TYPE_INCOMING,
    SHEET_TYPE_OUTGOING,
    SHEET_TYPE_SKIP,
    SHEET_TYPES,
)

_SKIP_OPTION = "(No existe / Omitir)"

# Campos de mapeo adicionales para hojas genéricas (incluye tipo_llamada)
_GENERIC_EXTRA_FIELDS: dict[str, str] = {
    COL_CALL_TYPE: "Tipo de Llamada (Ej: entrante/saliente/datos)",
}


class SheetColumnMapperDialog(tk.Toplevel):
    """
    Diálogo modal con pestañas: una por hoja del Excel.

    Cada pestaña permite:
    - Asignar el tipo de hoja (Entrantes, Salientes, Datos, Genérica, Ignorar)
    - Mapear columnas del Excel a los campos internos del sistema

    Resultado disponible en `self.result` tras cerrar:
    - list[SheetConfig] si el usuario confirmó
    - None si canceló
    """

    def __init__(
        self,
        parent: tk.Misc,
        sheets: dict[str, list[str]],
        loaded_status: Optional[dict[str, int]] = None,
    ) -> None:
        """
        Args:
            parent: ventana padre.
            sheets: {nombre_hoja: [columnas_disponibles]}.
            loaded_status: datos ya cargados {tipo: cantidad}, p.ej.
                           {"Entrantes": 120, "Salientes": 80, "Datos": 0}.
        """
        super().__init__(parent)
        self.title("Configuración de Hojas y Columnas")
        self.geometry("700x720")
        self.minsize(680, 640)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._sheets = sheets
        self._loaded_status = loaded_status or {}
        self.result: Optional[list[dict]] = None

        # Estado por hoja: {sheet_name: {type_var, combos, frame}}
        self._sheet_state: dict[str, dict] = {}

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ── Construcción de UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=(16, 12, 16, 12))
        root.pack(fill="both", expand=True)

        is_single = len(self._sheets) == 1

        ttk.Label(
            root,
            text="Configuración de Hojas y Columnas",
            font=("Arial", 12, "bold"),
        ).pack(pady=(0, 4))

        # Mostrar estado de datos ya cargados (si aplica)
        if self._loaded_status and any(v > 0 for v in self._loaded_status.values()):
            status_frame = ttk.LabelFrame(
                root, text="Datos ya cargados", padding=6
            )
            status_frame.pack(fill="x", pady=(0, 8))

            parts = []
            for tipo, count in self._loaded_status.items():
                mark = "\u2713" if count > 0 else "\u2717"
                parts.append(f" {mark} {tipo}: {count}")
            status_text = "   |   ".join(parts)

            ttk.Label(
                status_frame,
                text=status_text,
                font=("Arial", 9),
                foreground="#155724",
            ).pack(anchor="w")

            ttk.Label(
                status_frame,
                text=(
                    "Los nuevos datos se sumarán a los ya existentes. "
                    "Puedes marcar como 'Ignorar' las hojas que ya tengas."
                ),
                font=("Arial", 8),
                foreground="gray",
                wraplength=640,
            ).pack(anchor="w", pady=(2, 0))

        if is_single:
            instructions = (
                "1. Selecciona el tipo de datos que contiene este archivo "
                "(Entrantes, Salientes, Datos, Genérica).\n"
                "2. Asigna las columnas del archivo a los campos del sistema.\n"
                "Los campos marcados con * son obligatorios."
            )
        else:
            instructions = (
                "Cada pestaña representa una hoja de tu archivo Excel.\n"
                "Asigna el tipo de cada hoja y mapea las columnas correspondientes.\n"
                "Los campos marcados con * son obligatorios."
            )

        ttk.Label(
            root,
            text=instructions,
            wraplength=640,
            justify="left",
        ).pack(pady=(0, 8), anchor="w")

        # Notebook con pestañas
        self._notebook = ttk.Notebook(root)
        self._notebook.pack(fill="both", expand=True, pady=(0, 8))

        for sheet_name, columns in self._sheets.items():
            self._build_sheet_tab(sheet_name, columns)

        # Botón confirmar
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", pady=(4, 0))
        ttk.Button(
            btn_frame, text="Confirmar y Cargar Todo", command=self._on_confirm
        ).pack(side="right", ipadx=20, ipady=5)

    def _build_sheet_tab(self, sheet_name: str, columns: list[str]) -> None:
        """Crea una pestaña para una hoja del Excel."""
        tab = ttk.Frame(self._notebook, padding=10)
        self._notebook.add(tab, text=f" {sheet_name} ")

        is_single = len(self._sheets) == 1

        # Tipo de hoja — resaltado para que el usuario lo note
        type_frame = ttk.LabelFrame(
            tab,
            text="¿Qué tipo de datos contiene?" if is_single else "Tipo de hoja",
            padding=8,
        )
        type_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(
            type_frame,
            text=(
                "Selecciona qué tipo de información tiene este archivo:"
                if is_single
                else "Tipo de hoja:"
            ),
            font=("Arial", 10, "bold"),
        ).pack(side="left", padx=(0, 10))

        type_var = tk.StringVar(value=self._auto_detect_type(sheet_name))
        type_combo = ttk.Combobox(
            type_frame,
            textvariable=type_var,
            values=list(SHEET_TYPES),
            state="readonly",
            width=20,
        )
        type_combo.pack(side="left")

        # Previsualización de columnas disponibles
        ttk.Label(
            tab,
            text=f"Columnas encontradas: {', '.join(columns[:8])}{'...' if len(columns) > 8 else ''}",
            foreground="gray",
            wraplength=620,
        ).pack(anchor="w", pady=(0, 6))

        # Contenedor de mapeo (scrollable)
        mapping_container = ttk.Frame(tab)
        mapping_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            mapping_container, borderwidth=0, highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            mapping_container, orient="vertical", command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        form = ttk.Frame(canvas, padding=5)
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")

        form.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(form_window, width=e.width),
        )
        form.grid_columnconfigure(1, weight=1)

        # Construir combos para los campos de mapeo
        combo_options = [_SKIP_OPTION] + list(columns)
        combos: dict[str, ttk.Combobox] = {}
        labels: dict[str, ttk.Label] = {}

        all_fields = dict(COLUMN_MAPPING_FIELDS)
        all_fields.update(_GENERIC_EXTRA_FIELDS)

        for row_idx, (internal, label) in enumerate(all_fields.items()):
            lbl = ttk.Label(form, text=f"  {label}:", anchor="w")
            lbl.grid(row=row_idx, column=0, sticky="w", pady=4, padx=5)
            labels[internal] = lbl

            combo = ttk.Combobox(
                form, values=combo_options, state="readonly", width=34
            )
            combo.grid(row=row_idx, column=1, pady=4, padx=5, sticky="ew")
            combos[internal] = combo

        # Guardar estado
        state = {
            "type_var": type_var,
            "combos": combos,
            "labels": labels,
            "form": form,
            "columns": columns,
        }
        self._sheet_state[sheet_name] = state

        # Auto-seleccionar columnas según tipo detectado
        self._apply_auto_selection(sheet_name)

        # Cuando cambia el tipo de hoja, re-auto-seleccionar
        type_var.trace_add(
            "write", lambda *_a, sn=sheet_name: self._on_type_changed(sn)
        )

        # Actualizar visibilidad de campos según el tipo
        self._update_field_visibility(sheet_name)

    # ── Auto-detección de tipo de hoja ────────────────────────────────────────

    def _auto_detect_type(self, sheet_name: str) -> str:
        """Detecta automáticamente el tipo de hoja según su nombre y columnas."""
        key = sheet_name.lower().strip()
        for sheet_type, keywords in SHEET_DETECT_KEYWORDS.items():
            if any(kw in key for kw in keywords):
                return sheet_type

        # Si el nombre no ayuda, intentar deducir por columnas
        columns = self._sheets.get(sheet_name, [])
        cols_lower = " ".join(c.lower() for c in columns)

        # Si tiene columna tipo_llamada / tipo_cdr → Genérica (el tipo viene en los datos)
        if any(kw in cols_lower for kw in ("tipo_llamada", "tipo_cdr", "call_type")):
            return SHEET_TYPE_GENERIC

        # Si tiene columna trafico_de_bajada o gprs → Datos
        if any(kw in cols_lower for kw in ("trafico", "gprs", "pdp", "descarga", "bajada")):
            return SHEET_TYPE_DATA

        return SHEET_TYPE_GENERIC

    # ── Auto-selección de columnas ────────────────────────────────────────────

    def _apply_auto_selection(self, sheet_name: str) -> None:
        """Auto-selecciona las columnas más probables para cada campo."""
        state = self._sheet_state[sheet_name]
        sheet_type = state["type_var"].get()
        columns = state["columns"]

        for internal, combo in state["combos"].items():
            self._auto_select_column(combo, internal, columns, sheet_type)

    def _auto_select_column(
        self,
        combo: ttk.Combobox,
        internal_name: str,
        columns: list[str],
        sheet_type: str,
    ) -> None:
        """Detecta automáticamente la columna del Excel más probable."""
        cell_keywords = ("celda", "site", "bts", "nom_", "ant", "nombre_celda")
        date_keywords = ("fecha", "date", "hora", "timestamp", "fecha_hora",
                         "fecha_trafico", "fecha_hora_inicio")
        origin_keywords = ("originador", "origen", "numero", "originat",
                           "calling", "a_number", "num_origen")
        dest_keywords = ("receptor", "destino", "destinat", "called",
                         "b_number", "num_destino")
        duration_keywords = ("duracion", "duration", "segundos", "dur_")
        lat_keywords = ("latitud", "lat", "latitude")
        lon_keywords = ("longitud", "lon", "lng", "longitude")
        type_keywords = ("tipo", "type", "cdr", "tipo_llamada", "tipo_cdr",
                         "call_type")

        keyword_map: dict[str, tuple[str, ...]] = {
            "nombre_celda": cell_keywords,
            "fecha_hora": date_keywords,
            "originador": origin_keywords,
            "receptor": dest_keywords,
            "duracion": duration_keywords,
            "latitud_n": lat_keywords,
            "longitud_w": lon_keywords,
            "tipo_llamada": type_keywords,
        }

        keywords = keyword_map.get(internal_name, ())
        if not keywords:
            # Fallback: usar el nombre base del campo
            base = internal_name.split("_")[0]
            keywords = (base,)

        for col in columns:
            clean = col.lower().replace("_", "").replace(" ", "").replace(".", "")
            for kw in keywords:
                kw_clean = kw.replace("_", "")
                if kw_clean in clean:
                    combo.set(col)
                    return

        combo.current(0)  # (No existe / Omitir)

    def _on_type_changed(self, sheet_name: str) -> None:
        """Cuando cambia el tipo de hoja, re-auto-seleccionar y actualizar visibilidad."""
        self._apply_auto_selection(sheet_name)
        self._update_field_visibility(sheet_name)

    def _update_field_visibility(self, sheet_name: str) -> None:
        """Actualiza los indicadores de campos obligatorios según el tipo de hoja."""
        state = self._sheet_state[sheet_name]
        sheet_type = state["type_var"].get()

        required = self._get_required_fields(sheet_type)

        all_fields = dict(COLUMN_MAPPING_FIELDS)
        all_fields.update(_GENERIC_EXTRA_FIELDS)

        stored_labels = state["labels"]
        stored_combos = state["combos"]

        for internal, label_text in all_fields.items():
            is_required = internal in required
            # Ocultar tipo_llamada para hojas que no son genéricas
            is_visible = True
            if internal == COL_CALL_TYPE and sheet_type != SHEET_TYPE_GENERIC:
                is_visible = False
            # Ocultar receptor para hojas de datos (se auto-rellena)
            if internal == COL_RECEIVER and sheet_type == SHEET_TYPE_DATA:
                is_visible = False

            lbl = stored_labels.get(internal)
            combo = stored_combos.get(internal)

            if lbl:
                if is_visible:
                    prefix = "*" if is_required else " "
                    lbl.configure(text=f"{prefix} {label_text}:")
                    lbl.grid()
                else:
                    lbl.grid_remove()

            if combo:
                if is_visible:
                    combo.grid()
                else:
                    combo.grid_remove()

    def _get_required_fields(self, sheet_type: str) -> frozenset[str]:
        """Devuelve los campos obligatorios según el tipo de hoja."""
        if sheet_type == SHEET_TYPE_DATA:
            return REQUIRED_MAPPING_FIELDS_DATA
        if sheet_type == SHEET_TYPE_GENERIC:
            return REQUIRED_MAPPING_FIELDS | frozenset({COL_CALL_TYPE})
        if sheet_type == SHEET_TYPE_SKIP:
            return frozenset()
        # Entrantes / Salientes
        return REQUIRED_MAPPING_FIELDS

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _on_confirm(self) -> None:
        result: list[dict] = []

        for sheet_name, state in self._sheet_state.items():
            sheet_type = state["type_var"].get()

            if sheet_type == SHEET_TYPE_SKIP:
                continue

            mapping: dict[str, str] = {}
            missing: list[str] = []
            required = self._get_required_fields(sheet_type)

            all_fields = dict(COLUMN_MAPPING_FIELDS)
            all_fields.update(_GENERIC_EXTRA_FIELDS)

            for internal, combo in state["combos"].items():
                # Saltar campos no visibles
                if internal == COL_CALL_TYPE and sheet_type != SHEET_TYPE_GENERIC:
                    continue
                if internal == COL_RECEIVER and sheet_type == SHEET_TYPE_DATA:
                    continue

                selected = combo.get()
                if selected and selected != _SKIP_OPTION:
                    mapping[internal] = selected
                elif internal in required:
                    missing.append(all_fields.get(internal, internal))

            if missing:
                # Ir a la pestaña con el error
                tab_idx = list(self._sheet_state.keys()).index(sheet_name)
                self._notebook.select(tab_idx)
                messagebox.showerror(
                    "Campos obligatorios",
                    f"Hoja '{sheet_name}' ({sheet_type}):\n\n"
                    "Los siguientes campos son obligatorios:\n\n"
                    + "\n".join(f"• {f}" for f in missing),
                )
                return

            result.append({
                "sheet_name": sheet_name,
                "sheet_type": sheet_type,
                "mapping": mapping,
            })

        if not result:
            messagebox.showwarning(
                "Sin hojas seleccionadas",
                "Debes seleccionar al menos una hoja para procesar.\n"
                "Cambia el tipo de alguna hoja a algo diferente de 'Ignorar'.",
            )
            return

        self.result = result
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
