import tkinter as tk
from tkinter import ttk, messagebox

class ColumnMapperDialog(tk.Toplevel):
    """
    Diálogo modal para mapear columnas de Excel a campos del sistema.
    """
    def __init__(self, parent, available_columns):
        super().__init__(parent)
        self.title("🔗 Mapeo de Columnas")
        self.geometry("550x550")
        self.transient(parent)
        self.grab_set()
        
        # Copia de columnas disponibles + opción de omitir
        self.available_columns = ["(No existe / Omitir)"] + list(available_columns)
        self.result = None  # Aquí guardaremos el mapeo final
        
        # Campos requeridos por tu sistema (Interno : Nombre para mostrar)
        self.required_fields = {
            "originador": "Número Origen",
            "receptor": "Número Destino",
            "fecha_hora": "Fecha y Hora",
            "duracion": "Duración (seg)",
            "nombre_celda": "Nombre Celda/Antena (Opcional para Mapa)", # <--- NUEVO
            "latitud_n": "Latitud (Decimal - Opcional)",
            "longitud_w": "Longitud (Decimal - Opcional)"
        }
        
        self.selections = {}
        self.create_widgets()

        # Protocolo para manejar el cierre con la X (cancelar)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
    def create_widgets(self):
        ttk.Label(self, text="⚠️ Configuración de Datos", font=("Arial", 11, "bold")).pack(pady=10)
        ttk.Label(self, text="Relaciona las columnas de tu Excel con los datos que necesita el sistema.", wraplength=500).pack(pady=(0, 15))
        
        frame_form = ttk.Frame(self, padding=10)
        frame_form.pack(fill="both", expand=True)
        
        row = 0
        for internal_name, human_name in self.required_fields.items():
            # Etiqueta del campo
            lbl = ttk.Label(frame_form, text=f"{human_name}:")
            lbl.grid(row=row, column=0, sticky="w", pady=5, padx=5)
            
            # Dropdown
            combo = ttk.Combobox(frame_form, values=self.available_columns, state="readonly", width=35)
            
            # --- AUTO-SELECCIÓN INTELIGENTE ---
            match_found = False
            for col in self.available_columns:
                if col == "(No existe / Omitir)": continue
                
                # Normalizamos nombres para comparar
                clean_col = col.lower().replace("_", "").replace(" ", "").replace(".", "")
                clean_internal = internal_name.split("_")[0] # ej: 'latitud' de 'latitud_n'
                
                # Excepción para nombre de celda (busca 'celda', 'site', 'bts', 'antena')
                if internal_name == "nombre_celda":
                    if any(x in clean_col for x in ['celda', 'site', 'bts', 'nom', 'ant']):
                        combo.set(col)
                        match_found = True
                        break
                
                # Si el nombre interno está en la columna del excel
                elif clean_internal in clean_col:
                    combo.set(col)
                    match_found = True
                    break
            
            if not match_found:
                combo.current(0) # Seleccionar "(No existe...)" por defecto
                
            combo.grid(row=row, column=1, pady=5, padx=5)
            self.selections[internal_name] = combo
            row += 1
            
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=20)
        
        ttk.Button(btn_frame, text="✅ Confirmar y Cargar", command=self.confirmar).pack(ipadx=10, ipady=5)
        
    def confirmar(self):
        mapping = {}
        missing_critical = []
        
        # Validar selecciones
        for internal, combo in self.selections.items():
            selected = combo.get()
            if selected != "(No existe / Omitir)":
                mapping[internal] = selected
            else:
                # Definir qué campos son OBLIGATORIOS (críticos)
                if internal in ["originador", "receptor", "fecha_hora"]:
                    missing_critical.append(self.required_fields[internal])
        
        if missing_critical:
            messagebox.showerror("Faltan datos", f"Los siguientes campos son obligatorios para continuar:\n\n• {', '.join(missing_critical)}")
            return

        self.result = mapping
        self.destroy() # Cierra la ventana y devuelve el control al main

    def on_cancel(self):
        self.result = None
        self.destroy()
