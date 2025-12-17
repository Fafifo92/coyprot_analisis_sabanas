# src/gui.py

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext, simpledialog
from ttkthemes import ThemedTk
import pandas as pd
import os
import shutil
import logging
import threading
import queue
import sys
import subprocess

# --- IMPORTACIONES LOCALES ---
try:
    from utils import configurar_logs, resource_path
except ImportError as e:
    print(f"ERROR CRÍTICO: No se pudo importar 'utils': {e}", file=sys.stderr)
    sys.exit(1)

try:
    from excel_utils import cargar_excel_crudo, procesar_dataframe_con_mapeo
    from column_mapper import ColumnMapperDialog 
    from report_generator import generar_informe_html, generar_datos_llamadas_json
    from geo_utils import generar_mapa_agrupado, generar_mapa_rutas, generar_mapa_calor
    from graphics_utils import generar_grafico_top_llamadas, generar_grafico_horario_llamadas
    from ftp_utils import subir_archivo_ftp
    from cell_geocoder import CellGeocoder 
except ImportError as e:
    print(f"ERROR CRÍTICO: Fallo importando módulos lógicos: {e}", file=sys.stderr)

# --- Constantes ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(APP_DIR, "output")

try:
    STATIC_DIR = os.path.join(APP_DIR, "static")
    LOGO_PATH = os.path.join(STATIC_DIR, "assets_img", "logo.png")
    INFO_PATH = os.path.join(STATIC_DIR, "assets_img", "info.png")
    DB_NAME = "celdas.csv"
except Exception as e:
    print(f"Error rutas estáticas: {e}")

# Credenciales FTP
FTP_HOST = "plcoyprot.com"
FTP_USER = "plcoypro"
FTP_PASS = "181955Danilo?"

# Categorías para los PDFs adjuntos
CATEGORIAS_PDF = ["Financiero", "Propiedades", "Vehículos", "Judicial", "Antecedentes", "Otros"]

# --- Clase Principal de la GUI ---
class CallAnalyzerGUI(ThemedTk):
    def __init__(self):
        super().__init__(theme="adapta") 
        self.title("📊 Analizador de Llamadas Pro v2.2")
        self.geometry("980x750")
        self.minsize(850, 650)

        # Variables
        self.df = None
        self.nombres_asignados = {}
        self.datos_generales = {} # Diccionario {Campo: Valor}
        self.lista_pdfs = [] 
        self.incluir_logo = tk.BooleanVar(value=True)
        self.subir_ftp = tk.BooleanVar(value=False)
        self.archivo_path = tk.StringVar()
        self.nombre_informe = tk.StringVar(value="Informe_Llamadas")
        self.work_queue = queue.Queue()
        self.is_processing = False

        # Configuración Logging
        self.log_text_widget = None
        self.logger = configurar_logs() 
        if not self.logger:
             messagebox.showerror("Error", "No se pudo iniciar logs.")
             self.destroy(); return

        # Widgets
        self.create_widgets()
        if self.log_text_widget: self._configure_gui_logging()

        # Geocoder
        db_path = os.path.join(STATIC_DIR, "db", DB_NAME)
        if os.path.exists(db_path):
            self.logger.info(f"🔄 Cargando base de datos de celdas desde: {DB_NAME}")
            self.geocoder = CellGeocoder(db_path)
        else:
            self.logger.warning(f"⚠️ No se encontró {DB_NAME}. Geolocalización desactivada.")
            self.geocoder = None

        self.logger.info("Interfaz lista.")
        self.after(100, self.process_queue)

    def _configure_gui_logging(self):
        class TextWidgetHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.widget = text_widget
                self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
                self.setLevel(logging.INFO)
            def emit(self, record):
                msg = self.format(record)
                try:
                    self.widget.config(state=tk.NORMAL)
                    self.widget.insert(tk.END, msg + '\n')
                    self.widget.config(state=tk.DISABLED)
                    self.widget.see(tk.END)
                except: pass
        self.logger.addHandler(TextWidgetHandler(self.log_text_widget))

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="15"); main_frame.pack(expand=True, fill=tk.BOTH)
        main_frame.grid_rowconfigure(4, weight=1) 
        main_frame.grid_columnconfigure(0, weight=1); main_frame.grid_columnconfigure(1, weight=1) 

        # 1. Carga
        f_load = ttk.LabelFrame(main_frame, text="📂 Archivo Principal", padding="15")
        f_load.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        f_load.grid_columnconfigure(1, weight=1)
        ttk.Label(f_load, text="Excel/CSV:").grid(row=0, column=0, padx=5, sticky="w")
        ttk.Entry(f_load, textvariable=self.archivo_path, width=70, state='readonly').grid(row=0, column=1, padx=10, sticky="ew")
        self.btn_cargar = ttk.Button(f_load, text="Seleccionar Archivo", command=self.cargar_archivo)
        self.btn_cargar.grid(row=0, column=2, padx=5)

        # 2. Adjuntos
        f_adj = ttk.LabelFrame(main_frame, text="📎 Adjuntos (PDF)", padding="10")
        f_adj.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        f_adj.grid_columnconfigure(0, weight=1)
        
        # Treeview mejorado con scroll
        self.tree_adj = ttk.Treeview(f_adj, columns=("cat", "arch"), show="headings", height=5)
        self.tree_adj.heading("cat", text="Categoría"); self.tree_adj.column("cat", width=180, anchor="center")
        self.tree_adj.heading("arch", text="Nombre del Archivo"); self.tree_adj.column("arch", width=600, anchor="w")
        self.tree_adj.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=5)
        
        scrol = ttk.Scrollbar(f_adj, orient="vertical", command=self.tree_adj.yview)
        self.tree_adj.configure(yscrollcommand=scrol.set); scrol.grid(row=0, column=1, rowspan=3, sticky="ns")
        
        f_btns = ttk.Frame(f_adj); f_btns.grid(row=0, column=2, sticky="n", padx=10)
        self.btn_add_pdf = ttk.Button(f_btns, text="➕ Agregar", command=self.agregar_pdf_adjunto); self.btn_add_pdf.pack(fill="x", pady=2)
        self.btn_del_pdf = ttk.Button(f_btns, text="⛔ Quitar", command=self.eliminar_pdf_adjunto); self.btn_del_pdf.pack(fill="x", pady=2)

        # 3. Opciones
        f_ops = ttk.LabelFrame(main_frame, text="⚙️ Procesamiento", padding="10")
        f_ops.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.btn_nombres = ttk.Button(f_ops, text="👤 Asignar Nombres/Alias", command=self.asignar_nombres, state=tk.DISABLED)
        self.btn_nombres.pack(fill="x", pady=5, ipady=3)
        self.btn_datos = ttk.Button(f_ops, text="📝 Datos del Caso", command=self.abrir_editor_datos, state=tk.DISABLED)
        self.btn_datos.pack(fill="x", pady=5, ipady=3)

        # 4. Exportar
        f_exp = ttk.LabelFrame(main_frame, text="🚀 Generar", padding="10")
        f_exp.grid(row=2, column=1, sticky="nsew", padx=5, pady=5); f_exp.grid_columnconfigure(1, weight=1)
        
        f_name = ttk.Frame(f_exp); f_name.pack(fill="x", pady=5)
        ttk.Label(f_name, text="Nombre Carpeta:").pack(side="left")
        ttk.Entry(f_name, textvariable=self.nombre_informe).pack(side="left", fill="x", expand=True, padx=10)
        
        f_chk = ttk.Frame(f_exp); f_chk.pack(fill="x", pady=5)
        ttk.Checkbutton(f_chk, text="Incluir Membretes", variable=self.incluir_logo).pack(side="left", padx=10)
        ttk.Checkbutton(f_chk, text="Subir a FTP", variable=self.subir_ftp).pack(side="left", padx=10)
        
        self.btn_export = ttk.Button(f_exp, text="💾 Generar y Exportar Informe", command=self.iniciar_exportacion, style="Accent.TButton", state=tk.DISABLED)
        self.btn_export.pack(fill="x", pady=10, ipady=5)

        try: ttk.Style().configure("Accent.TButton", font=('Helvetica', 10, 'bold'))
        except: pass

        # 5. Logs
        f_log = ttk.LabelFrame(main_frame, text="📋 Registro de Actividad", padding="10")
        f_log.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        f_log.grid_rowconfigure(0, weight=1); f_log.grid_columnconfigure(0, weight=1)
        self.log_text_widget = scrolledtext.ScrolledText(f_log, wrap=tk.WORD, height=8, state='disabled', font=('Consolas', 9))
        self.log_text_widget.grid(row=0, column=0, sticky="nsew")

    # --- LÓGICA DE ADJUNTOS (Igual que antes) ---
    def agregar_pdf_adjunto(self):
        if self.is_processing: return
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not path: return
        cat = self.pedir_categoria_dialogo()
        if not cat: return 
        fname = os.path.basename(path)
        self.lista_pdfs.append({"categoria": cat, "ruta": path, "nombre_archivo": fname})
        self.tree_adj.insert("", "end", values=(cat, fname))
        self.logger.info(f"📎 Adjuntado: {fname} ({cat})")

    def pedir_categoria_dialogo(self):
        d = tk.Toplevel(self); d.title("Categoría"); d.geometry("300x150"); d.transient(self); d.grab_set()
        self.cat_sel = None
        ttk.Label(d, text="Tipo de documento:").pack(pady=10)
        c = ttk.Combobox(d, values=CATEGORIAS_PDF, state="readonly"); c.pack(pady=5, padx=10, fill="x"); c.current(0)
        def ok(): self.cat_sel = c.get(); d.destroy()
        ttk.Button(d, text="Aceptar", command=ok).pack(pady=10)
        self.wait_window(d)
        return self.cat_sel

    def eliminar_pdf_adjunto(self):
        sel = self.tree_adj.selection()
        if not sel: return
        for item in sel:
            v = self.tree_adj.item(item, "values")
            self.lista_pdfs = [p for p in self.lista_pdfs if not (p["nombre_archivo"] == v[1] and p["categoria"] == v[0])]
            self.tree_adj.delete(item)
            self.logger.info(f"🗑️ Eliminado: {v[1]}")

    # --- CARGA (Igual) ---
    def cargar_archivo(self):
        if self.is_processing: return
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls *.csv")])
        if path:
            self.archivo_path.set(path)
            self.is_processing = True
            self.bloquear_botones(True)
            self.logger.info(f"Cargando: {os.path.basename(path)}")
            threading.Thread(target=self._thread_cargar, args=(path,), daemon=True).start()

    def _thread_cargar(self, path):
        try:
            df_raw, err = cargar_excel_crudo(path)
            if df_raw is None: self.work_queue.put(("error", err)); return
            self.work_queue.put(("pedir_mapeo", df_raw))
        except Exception as e:
            self.work_queue.put(("error", str(e)))

    def continuar_carga_con_mapeo(self, df_raw):
        d = ColumnMapperDialog(self, df_raw.columns)
        self.wait_window(d)
        if not d.result:
            self.logger.warning("Cancelado."); self.is_processing = False; self.bloquear_botones(False); return
        threading.Thread(target=self._thread_proceso_final, args=(df_raw, d.result), daemon=True).start()

    def _thread_proceso_final(self, df_raw, mapping):
        try:
            self.logger.info("Procesando datos...")
            self.df = procesar_dataframe_con_mapeo(df_raw, mapping)
            if self.df is not None and self.geocoder:
                if "nombre_celda" in self.df.columns and not self.df.get("latitud_n", pd.Series()).notna().any():
                     self.logger.info("Geolocalizando...")
                     self.df = self.geocoder.buscar_coordenadas(self.df, "nombre_celda")
            self.work_queue.put(("carga_ok", len(self.df)))
        except Exception as e:
            self.work_queue.put(("error", f"Error proceso: {e}"))

    # --- NUEVA VENTANA: ASIGNAR NOMBRES (MEJORADA) ---
    def asignar_nombres(self):
        if self.df is None: return
        numeros = sorted(list(set(self.df['originador'].dropna().astype(str).unique()) | set(self.df['receptor'].dropna().astype(str).unique())))
        
        w = tk.Toplevel(self); w.title(f"👤 Asignar Nombres ({len(numeros)} Números)")
        w.geometry("600x700"); w.transient(self); w.grab_set()

        # Buscador
        f_search = ttk.Frame(w, padding="10"); f_search.pack(fill="x")
        ttk.Label(f_search, text="🔍 Buscar:").pack(side="left")
        search_var = tk.StringVar()
        entry_search = ttk.Entry(f_search, textvariable=search_var)
        entry_search.pack(side="left", fill="x", expand=True, padx=5)

        # Canvas Scroll
        f_main = ttk.Frame(w); f_main.pack(fill="both", expand=True)
        canv = tk.Canvas(f_main, bg="#f9f9f9"); s = ttk.Scrollbar(f_main, command=canv.yview)
        frm_list = ttk.Frame(canv); frm_list.bind("<Configure>", lambda e: canv.configure(scrollregion=canv.bbox("all")))
        canv.create_window((0,0), window=frm_list, anchor="nw"); canv.configure(yscrollcommand=s.set)
        canv.pack(side="left", fill="both", expand=True); s.pack(side="right", fill="y")
        
        # Diccionario para guardar referencias a los Entry widgets
        self.entry_widgets = {} 
        
        def render_list(filter_text=""):
            # Limpiar frame
            for widget in frm_list.winfo_children(): widget.destroy()
            self.entry_widgets = {}

            row_idx = 0
            for num in numeros:
                # Filtrado
                alias_actual = self.nombres_asignados.get(num, "")
                if filter_text and filter_text.lower() not in num.lower() and filter_text.lower() not in alias_actual.lower():
                    continue

                # Estilo fila
                bg = "#ffffff" if row_idx % 2 == 0 else "#f0f0f0"
                f_row = tk.Frame(frm_list, bg=bg, pady=2); f_row.pack(fill="x", expand=True)
                
                lbl = tk.Label(f_row, text=num, width=20, anchor="w", bg=bg, font=('Arial', 10, 'bold'))
                lbl.pack(side="left", padx=10)
                
                v = tk.StringVar(value=alias_actual)
                e = ttk.Entry(f_row, textvariable=v, width=40)
                e.pack(side="left", fill="x", expand=True, padx=10)
                
                # Guardar referencia
                self.entry_widgets[num] = v
                row_idx += 1

        # Render inicial
        render_list()

        # Evento búsqueda
        search_var.trace("w", lambda *args: render_list(search_var.get()))

        # Botón Guardar Flotante
        f_bot = ttk.Frame(w, padding="10"); f_bot.pack(fill="x")
        def save():
            # Actualizar diccionario principal con lo que hay en los widgets visibles Y mantener lo previo
            for num, var in self.entry_widgets.items():
                val = var.get().strip()
                if val: self.nombres_asignados[num] = val
                elif num in self.nombres_asignados: del self.nombres_asignados[num] # Borrar si se limpia
            
            self.logger.info(f"Nombres actualizados: {len(self.nombres_asignados)}")
            messagebox.showinfo("Guardado", "Nombres asignados correctamente."); w.destroy()

        ttk.Button(f_bot, text="💾 Guardar Cambios", command=save, style="Accent.TButton").pack(fill="x", ipady=5)


    # --- NUEVA VENTANA: DATOS GENERALES (MEJORADA) ---
    def abrir_editor_datos(self):
        w = tk.Toplevel(self); w.title("📝 Datos del Caso"); w.geometry("500x600"); w.transient(self); w.grab_set()
        
        f_main = ttk.Frame(w, padding="15"); f_main.pack(fill="both", expand=True)
        ttk.Label(f_main, text="Información General del Informe", font=("Arial", 12, "bold")).pack(pady=(0, 15))

        # Canvas Scroll
        f_canv = ttk.Frame(f_main); f_canv.pack(fill="both", expand=True)
        cv = tk.Canvas(f_canv, bg="white", height=300); sb = ttk.Scrollbar(f_canv, command=cv.yview)
        f_items = ttk.Frame(cv); f_items.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=f_items, anchor="nw", width=440); cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        # Almacén de referencias
        self.datos_entries = {} # key: (label_var, entry_var)

        def add_row(k="", v=""):
            row_id = len(self.datos_entries) + 1 # ID único simple
            f_row = ttk.Frame(f_items); f_row.pack(fill="x", pady=2)
            
            # Botón Eliminar
            btn_del = ttk.Button(f_row, text="✖", width=3, command=lambda: remove_row(row_id, f_row))
            btn_del.pack(side="left", padx=(0, 5))

            # Campo Clave (Editable si es nuevo, Fijo si es default?) -> Mejor editable todo
            k_var = tk.StringVar(value=k)
            e_key = ttk.Entry(f_row, textvariable=k_var, width=18, font=('Arial', 9, 'bold'))
            e_key.pack(side="left", padx=2)
            ttk.Label(f_row, text=":").pack(side="left")
            
            # Campo Valor
            v_var = tk.StringVar(value=v)
            e_val = ttk.Entry(f_row, textvariable=v_var)
            e_val.pack(side="left", fill="x", expand=True, padx=5)

            self.datos_entries[row_id] = (k_var, v_var)

        def remove_row(rid, widget):
            if rid in self.datos_entries: del self.datos_entries[rid]
            widget.destroy()

        # Cargar datos existentes o defaults
        defaults = ["Cliente", "Ciudad", "Teléfono", "Caso", "Periodo"]
        
        # Primero cargar lo que ya existe en self.datos_generales
        existing_keys = set(self.datos_generales.keys())
        
        # Ordenar: Primero defaults, luego el resto
        for k in defaults:
            val = self.datos_generales.get(k, "")
            add_row(k, val)
            if k in existing_keys: existing_keys.remove(k)
        
        for k in existing_keys:
            add_row(k, self.datos_generales[k])

        # Botones de Acción
        f_acts = ttk.Frame(w, padding="15"); f_acts.pack(fill="x")
        ttk.Button(f_acts, text="➕ Agregar Campo Nuevo", command=lambda: add_row("", "")).pack(fill="x", pady=5)
        
        def save_all():
            new_data = {}
            for k_var, v_var in self.datos_entries.values():
                key = k_var.get().strip()
                val = v_var.get().strip()
                if key: new_data[key] = val
            
            self.datos_generales = new_data
            self.logger.info("Datos generales actualizados.")
            w.destroy()

        ttk.Button(f_acts, text="💾 Guardar y Cerrar", command=save_all, style="Accent.TButton").pack(fill="x", pady=10)

    # --- EXPORTAR (Igual que antes) ---
    def iniciar_exportacion(self):
        if self.is_processing or self.df is None: return
        name = self.nombre_informe.get().strip().replace(" ", "_") or "Informe_Llamadas"
        self.is_processing = True; self.bloquear_botones(True)
        self.btn_export.config(text="⚙️ Trabajando...")
        threading.Thread(target=self._thread_export, args=(name,), daemon=True).start()

    def _thread_export(self, name):
        try:
            self.logger.info(f"Generando informe: {name}")
            base_dir = generar_informe_html(self.df, name, self.incluir_logo.get(), LOGO_PATH, self.lista_pdfs, self.nombres_asignados, self.datos_generales)
            
            json_p = os.path.join(base_dir, "data", "call_data.js")
            generar_datos_llamadas_json(self.df, json_p, self.nombres_asignados)
            
            g_dir = os.path.join(base_dir, "graphics"); os.makedirs(g_dir, exist_ok=True)
            ent = self.df[self.df["tipo_llamada"] == "entrante"]
            sal = self.df[self.df["tipo_llamada"] == "saliente"]
            
            if not ent.empty: generar_grafico_top_llamadas(ent, "originador", "Recibidas", os.path.join(g_dir, "top_llamadas_recibidas.png"), self.nombres_asignados)
            if not sal.empty: generar_grafico_top_llamadas(sal, "receptor", "Realizadas", os.path.join(g_dir, "top_llamadas_realizadas.png"), self.nombres_asignados)
            generar_grafico_horario_llamadas(self.df, os.path.join(g_dir, "grafico_horario_llamadas.png"))

            if "latitud_n" in self.df.columns and self.df["latitud_n"].notna().any():
                 m_dir = os.path.join(base_dir, "maps")
                 generar_mapa_agrupado(self.df, os.path.join(m_dir, "mapa_agrupado.html"), self.nombres_asignados)
                 generar_mapa_rutas(self.df, os.path.join(m_dir, "mapa_rutas.html"), self.nombres_asignados)
                 generar_mapa_calor(self.df, os.path.join(m_dir, "mapa_calor.html"))

            if self.subir_ftp.get():
                self.work_queue.put(("status", "📡 Subiendo FTP..."))
                ok = subir_archivo_ftp(FTP_HOST, FTP_USER, FTP_PASS, base_dir, name)
                if ok is True: 
                    url = f"https://{FTP_HOST}/{name}/reports/informe_llamadas.html"
                    self.work_queue.put(("ftp_ok", url))
                else: raise Exception(f"FTP Error: {ok}")
            else:
                final_path = os.path.join(base_dir, "reports", "informe_llamadas.html")
                self.work_queue.put(("local_ok", final_path))

        except Exception as e:
            self.work_queue.put(("error", str(e)))

    # --- Queue Loop ---
    def process_queue(self):
        try:
            while True:
                msg = self.work_queue.get_nowait()
                tipo = msg[0]
                
                if tipo == "pedir_mapeo": self.continuar_carga_con_mapeo(msg[1])
                elif tipo == "carga_ok": 
                    self.logger.info(f"Cargado: {msg[1]}")
                    messagebox.showinfo("OK", f"Registros: {msg[1]}")
                    self.is_processing = False; self.bloquear_botones(False)
                elif tipo == "error": 
                    self.logger.error(msg[1]); messagebox.showerror("Error", msg[1])
                    self.is_processing = False; self.bloquear_botones(False)
                elif tipo == "status": self.btn_export.config(text=msg[1])
                elif tipo == "local_ok":
                    self.is_processing = False; self.bloquear_botones(False)
                    self.btn_export.config(text="💾 Generar")
                    if messagebox.askyesno("Éxito", f"Guardado en:\n{msg[1]}\n¿Abrir?"):
                        try: os.startfile(msg[1])
                        except: pass
                elif tipo == "ftp_ok":
                    self.is_processing = False; self.bloquear_botones(False)
                    self.btn_export.config(text="💾 Generar")
                    self.mostrar_url(msg[1])
        except queue.Empty: pass
        finally: self.after(100, self.process_queue)

    def bloquear_botones(self, bloquear):
        s = tk.DISABLED if bloquear else tk.NORMAL
        for b in [self.btn_cargar, self.btn_add_pdf, self.btn_del_pdf, self.btn_export]: b.config(state=s)
        if not bloquear and self.df is not None:
            self.btn_nombres.config(state=tk.NORMAL)
            self.btn_datos.config(state=tk.NORMAL)

    def mostrar_url(self, url):
        w = tk.Toplevel(self); w.title("URL"); w.geometry("600x150")
        ttk.Entry(w, width=70).pack(pady=10).insert(0, url)
        ttk.Button(w, text="Copiar", command=lambda: [self.clipboard_clear(), self.clipboard_append(url)]).pack()

if __name__ == "__main__":
    app = CallAnalyzerGUI()
    app.mainloop()