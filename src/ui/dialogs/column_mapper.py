"""
Diálogo de mapeo de columnas.

Permite al usuario relacionar las columnas de su Excel con los
campos internos del sistema.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from config.constants import COLUMN_MAPPING_FIELDS, REQUIRED_MAPPING_FIELDS

_SKIP_OPTION = "(No existe / Omitir)"


class ColumnMapperDialog(tk.Toplevel):
    """
    Diálogo modal para mapeo de columnas Excel → sistema.

    Resultado disponible en `self.result` tras cerrar:
    - dict {nombre_interno: columna_excel} si el usuario confirmó
    - None si canceló o cerró sin confirmar
    """

    def __init__(self, parent: tk.Misc, available_columns: list[str]) -> None:
        super().__init__(parent)
        self.title("Mapeo de Columnas")
        self.geometry("580x620")
        self.minsize(560, 520)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._columns = [_SKIP_OPTION] + list(available_columns)
        self.result: Optional[dict[str, str]] = None
        self._selections: dict[str, ttk.Combobox] = {}

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ── Construcción de UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=(16, 12, 16, 12))
        root.pack(fill="both", expand=True)

        ttk.Label(
            root,
            text="Configuración de Columnas",
            font=("Arial", 11, "bold"),
        ).pack(pady=(0, 10))

        ttk.Label(
            root,
            text=(
                "Relaciona las columnas de tu archivo Excel/CSV con los\n"
                "datos que necesita el sistema.\n"
                "Los campos marcados con * son obligatorios."
            ),
            wraplength=520,
            justify="left",
        ).pack(pady=(0, 10), anchor="w")

        content = ttk.Frame(root)
        content.pack(fill="both", expand=True)

        canvas = tk.Canvas(content, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        form = ttk.Frame(canvas, padding=10)
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")

        form.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(form_window, width=event.width),
        )

        form.grid_columnconfigure(1, weight=1)

        for row_idx, (internal, label) in enumerate(COLUMN_MAPPING_FIELDS.items()):
            is_required = internal in REQUIRED_MAPPING_FIELDS
            display = f"{'*' if is_required else ' '} {label}:"
            ttk.Label(form, text=display, anchor="w").grid(
                row=row_idx, column=0, sticky="w", pady=6, padx=5
            )

            combo = ttk.Combobox(
                form, values=self._columns, state="readonly", width=36
            )
            self._auto_select(combo, internal)
            combo.grid(row=row_idx, column=1, pady=6, padx=5, sticky="ew")
            self._selections[internal] = combo

        ttk.Label(form, text="* Campo obligatorio", foreground="gray").grid(
            row=len(COLUMN_MAPPING_FIELDS), column=0, columnspan=2, sticky="w", padx=5
        )

        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(
            btn_frame, text="Confirmar y Cargar", command=self._on_confirm
        ).pack(side="right", ipadx=20, ipady=5)

    # ── Auto-selección ────────────────────────────────────────────────────────

    def _auto_select(self, combo: ttk.Combobox, internal_name: str) -> None:
        """Detecta automáticamente la columna más probable del Excel."""
        base = internal_name.split("_")[0]

        cell_keywords = ("celda", "site", "bts", "nom", "ant")

        for col in self._columns:
            if col == _SKIP_OPTION:
                continue
            clean = col.lower().replace("_", "").replace(" ", "").replace(".", "")

            if internal_name == "nombre_celda":
                if any(kw in clean for kw in cell_keywords):
                    combo.set(col)
                    return
            elif base in clean:
                combo.set(col)
                return

        combo.current(0)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _on_confirm(self) -> None:
        mapping: dict[str, str] = {}
        missing: list[str] = []

        for internal, combo in self._selections.items():
            selected = combo.get()
            if selected != _SKIP_OPTION:
                mapping[internal] = selected
            elif internal in REQUIRED_MAPPING_FIELDS:
                missing.append(COLUMN_MAPPING_FIELDS[internal])

        if missing:
            messagebox.showerror(
                "Campos obligatorios",
                "Los siguientes campos son obligatorios:\n\n"
                + "\n".join(f"• {f}" for f in missing),
            )
            return

        self.result = mapping
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
