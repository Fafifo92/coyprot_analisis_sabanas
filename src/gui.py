# src/gui.py

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from ttkthemes import ThemedTk
import pandas as pd
import os
import shutil
import logging
from utils import configurar_logs

# --- IMPORTACIONES PROPIAS ---
# Nota: Asegúrate de que excel_utils.py y column_mapper.py estén actualizados
from excel_utils import cargar_excel_crudo, procesar_dataframe_con_mapeo
from column_mapper import ColumnMapperDialog 
from report_generator import generar_informe_html, generar_datos_llamadas_json
from geo_utils import generar_mapa_interactivo, generar_mapa_calor
from graphics_utils import generar_grafico_top_llamadas, generar_grafico_horario_llamadas
from ftp_utils import subir_archivo_ftp

# --- Constantes ---
SRC_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(SRC_DIR)
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
STATIC_DIR = os.path.join(ROOT_DIR, "static")
LOGO_PATH = os.path.join(STATIC_DIR, "assets_img", "logo.png")
INFO_PATH = os.path.join(STATIC_DIR, "assets_img", "info.png")

# Credenciales FTP
FTP_HOST = "plcoyprot.com"
FTP_USER = "plcoypro"
FTP_PASS = "181955Danilo?"

# --- Clase Principal de la GUI ---
class CallAnalyzerGUI(ThemedTk):
    def __init__(self):
        # Configuración inicial de la ventana con tema
        super().__init__(theme="adapta") 
        self.title("📊 Analizador de Llamadas Pro")
        self.geometry("850x700")
        self.minsize(700, 550)

        # --- Variables de Estado ---
        self.df = None
        self.nombres_asignados = {}
        self.datos_generales = {}
        self.incluir_logo = tk.BooleanVar(value=True)
        self.subir_ftp = tk.BooleanVar(value=False)
        self.archivo_path = tk.StringVar()
        self.pdf_path = tk.StringVar()
        self.nombre_informe = tk.StringVar(value="Informe_Llamadas")

        # --- Configuración del Logging ---
        self.log_text_widget = None
        self.logger = configurar_logs() 

        # --- Crear Widgets ---
        self.create_widgets()

        # --- Configurar Logger para GUI ---
        if self.log_text_widget:
            self._configure_gui_logging()

        self.logger.info("Interfaz gráfica iniciada.")

    def _configure_gui_logging(self):
        """Configura el handler para enviar logs al widget Text."""
        class TextWidgetHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                self.text_widget.configure(state='normal')
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.configure(state='disabled')
                self.text_widget.see(tk.END)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        text_handler = TextWidgetHandler(self.log_text_widget)
        text_handler.setFormatter(formatter)
        text_handler.setLevel(logging.INFO)
        self.logger.addHandler(text_handler)

    def create_widgets(self):
        """Crea y organiza los widgets en la ventana principal."""
        main_frame = ttk.Frame(self, padding="10 10 10 10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        main_frame.grid_rowconfigure(3, weight=1) 
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1) 

        # --- Sección de Carga de Archivos ---
        frame_cargar = ttk.LabelFrame(main_frame, text="📂 Archivos de Entrada", padding="10")
        frame_cargar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        frame_cargar.grid_columnconfigure(1, weight=1)

        ttk.Label(frame_cargar, text="Archivo Excel:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry_archivo = ttk.Entry(frame_cargar, textvariable=self.archivo_path, width=60)
        entry_archivo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        btn_cargar = ttk.Button(frame_cargar, text="Seleccionar Excel", command=self.cargar_archivo)
        btn_cargar.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(frame_cargar, text="PDF Financiero (Opcional):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        entry_pdf = ttk.Entry(frame_cargar, textvariable=self.pdf_path, width=60)
        entry_pdf.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        btn_pdf = ttk.Button(frame_cargar, text="Seleccionar PDF", command=self.seleccionar_pdf)
        btn_pdf.grid(row=1, column=2, padx=5, pady=5)

        # --- Sección de Opciones ---
        frame_opciones = ttk.LabelFrame(main_frame, text="⚙️ Opciones de Procesamiento", padding="10")
        frame_opciones.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        frame_opciones.grid_columnconfigure(0, weight=1)

        self.boton_nombres = ttk.Button(frame_opciones, text="👤 Asignar Nombres a Números", command=self.asignar_nombres, state=tk.DISABLED)
        self.boton_nombres.grid(row=0, column=0, pady=5, padx=10, sticky="ew")

        self.boton_datos = ttk.Button(frame_opciones, text="📝 Añadir Datos Generales al Informe", command=self.abrir_editor_datos, state=tk.DISABLED)
        self.boton_datos.grid(row=1, column=0, pady=5, padx=10, sticky="ew")

        # --- Sección de Exportación ---
        frame_exportar = ttk.LabelFrame(main_frame, text="🚀 Exportar Informe", padding="10")
        frame_exportar.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        frame_exportar.grid_columnconfigure(1, weight=1)

        ttk.Label(frame_exportar, text="Nombre del Informe:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry_nombre_informe = ttk.Entry(frame_exportar, textvariable=self.nombre_informe, width=30)
        entry_nombre_informe.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        frame_checks = ttk.Frame(frame_exportar)
        frame_checks.grid(row=1, column=0, columnspan=2, pady=5, sticky="w")
        chk_logo = ttk.Checkbutton(frame_checks, text="Incluir Membretes (Logo/Info)", variable=self.incluir_logo)
        chk_logo.pack(side=tk.LEFT, padx=5)
        chk_ftp = ttk.Checkbutton(frame_checks, text="Subir a FTP", variable=self.subir_ftp)
        chk_ftp.pack(side=tk.LEFT, padx=5)

        self.boton_exportar = ttk.Button(frame_exportar, text="💾 Generar y Exportar Informe", command=self.exportar_informe, style="Accent.TButton")
        self.boton_exportar.grid(row=2, column=0, columnspan=2, pady=10, padx=5, ipady=5, sticky="ew")

        # Estilo
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('Helvetica', 10, 'bold'))
        except tk.TclError:
            pass

        # --- Sección de Logs ---
        frame_log = ttk.LabelFrame(main_frame, text="📋 Registro de Actividad", padding="10")
        frame_log.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        frame_log.grid_rowconfigure(0, weight=1)
        frame_log.grid_columnconfigure(0, weight=1)

        self.log_text_widget = scrolledtext.ScrolledText(frame_log, wrap=tk.WORD, height=10, state='disabled', font=('Consolas', 9))
        self.log_text_widget.grid(row=0, column=0, sticky="nsew")

    def seleccionar_pdf(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Reporte Financiero PDF",
            filetypes=[("Archivos PDF", "*.pdf")]
        )
        if filepath:
            self.pdf_path.set(filepath)
            self.logger.info(f"Archivo PDF seleccionado: {os.path.basename(filepath)}")

    def cargar_archivo(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Archivo Excel de Llamadas",
            filetypes=[("Archivos Excel", "*.xlsx *.xls")]
        )
        if filepath:
            self.archivo_path.set(filepath)
            self.logger.info(f"Cargando archivo: {os.path.basename(filepath)}...")
            self.update_idletasks()
            
            # 1. Cargar datos crudos
            df_raw, error = cargar_excel_crudo(filepath)
            
            if df_raw is None:
                messagebox.showerror("Error", f"No se pudo leer el Excel: {error}")
                return

            # 2. Verificar columnas requeridas automáticamente
            required_std = ["originador", "receptor", "fecha_hora", "duracion", "latitud_n", "longitud_w"]
            cols_excel_norm = [c.lower().strip() for c in df_raw.columns]
            
            mapping = {}
            for req in required_std:
                if req in cols_excel_norm:
                    idx = cols_excel_norm.index(req)
                    mapping[req] = df_raw.columns[idx]
            
            # Verificar si faltan columnas críticas o si el mapeo está incompleto
            cols_found = list(mapping.keys())
            critical_missing = [c for c in ["originador", "receptor", "fecha_hora"] if c not in cols_found]
            
            # Si falta algo crítico o el usuario quiere asegurarse, abrimos el mapeador
            if critical_missing or len(cols_found) < len(required_std):
                self.logger.info("Columnas no coinciden exactamente. Abriendo asistente de mapeo...")
                
                # --- AQUÍ USAMOS EL MAPPER ---
                dialog = ColumnMapperDialog(self, df_raw.columns)
                self.wait_window(dialog)
                
                if dialog.result:
                    mapping = dialog.result
                else:
                    self.logger.warning("Carga cancelada por el usuario en el mapeo.")
                    return

            # 3. Procesar el DF con el mapeo confirmado
            self.df = procesar_dataframe_con_mapeo(df_raw, mapping)
            
            if self.df is not None and not self.df.empty:
                # Verificar coordenadas
                has_coords = "latitud_n" in self.df.columns and "longitud_w" in self.df.columns
                msg_extra = "📍 Coordenadas detectadas." if has_coords else "⚠️ Sin coordenadas (No se generarán mapas)."
                
                self.logger.info(f"✅ Datos listos. {len(self.df)} filas. {msg_extra}")
                messagebox.showinfo("Carga Exitosa", f"Datos procesados correctamente.\n{len(self.df)} registros.\n{msg_extra}")
                
                self.boton_nombres.config(state=tk.NORMAL)
                self.boton_datos.config(state=tk.NORMAL)
            else:
                messagebox.showerror("Error", "El procesamiento de datos falló.")

    def asignar_nombres(self):
        if self.df is None:
            messagebox.showwarning("Datos no cargados", "Primero carga un archivo Excel.")
            return

        # Obtener números únicos y ordenarlos
        numeros = set(self.df['originador'].dropna().astype(str).unique())
        if 'receptor' in self.df.columns:
            numeros.update(self.df['receptor'].dropna().astype(str).unique())
        
        numeros = sorted(list(numeros))

        ventana_nombres = tk.Toplevel(self)
        ventana_nombres.title("👤 Asignar Nombres a Números")
        ventana_nombres.geometry("550x550")
        ventana_nombres.transient(self)
        ventana_nombres.grab_set()

        main_frame = ttk.Frame(ventana_nombres, padding="10")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="Asigna un nombre (alias) a cada número:", font="-weight bold").pack(pady=(0, 10))

        # Scrollbar
        frame_canvas = ttk.Frame(main_frame)
        frame_canvas.pack(fill="both", expand=True)
        canvas = tk.Canvas(frame_canvas, borderwidth=0, background="#ffffff")
        scrollbar = ttk.Scrollbar(frame_canvas, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, padding="5")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.nombre_vars = {}
        scroll_frame.grid_columnconfigure(1, weight=1)
        for i, numero in enumerate(numeros):
            ttk.Label(scroll_frame, text=str(numero), width=20, anchor="w").grid(row=i, column=0, padx=5, pady=3, sticky="w")
            nombre_var = tk.StringVar(value=self.nombres_asignados.get(str(numero), ""))
            self.nombre_vars[str(numero)] = nombre_var
            ttk.Entry(scroll_frame, textvariable=nombre_var, width=35).grid(row=i, column=1, padx=5, pady=3, sticky="ew")

        ttk.Button(main_frame, text="Guardar Nombres", command=lambda: self.guardar_nombres(ventana_nombres)).pack(pady=10)

    def guardar_nombres(self, ventana):
        self.nombres_asignados = {num: var.get().strip() for num, var in self.nombre_vars.items() if var.get().strip()}
        self.logger.info(f"Nombres asignados actualizados: {len(self.nombres_asignados)} nombres guardados.")
        ventana.destroy()

    def abrir_editor_datos(self):
        """Abre una ventana para editar datos generales del informe."""
        ventana = tk.Toplevel(self)
        ventana.title("📝 Datos Generales del Informe")
        ventana.geometry("450x450")
        ventana.transient(self)
        ventana.grab_set()

        main_frame = ttk.Frame(ventana, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Añade información general que aparecerá en el informe:", font="-weight bold").pack(pady=(0, 10))

        # Frame Scroll
        frame_scrollable = ttk.Frame(main_frame)
        frame_scrollable.pack(fill=tk.BOTH, expand=True, pady=5)
        canvas = tk.Canvas(frame_scrollable, borderwidth=0, background="#ffffff")
        scrollbar = ttk.Scrollbar(frame_scrollable, orient="vertical", command=canvas.yview)
        self.frame_datos = ttk.Frame(canvas, padding="5")
        self.frame_datos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.frame_datos, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.campos_generales = {}
        campos_predeterminados = ["Nombre Cliente", "Ciudad", "Teléfono Contacto", "Dirección", "Referencia Caso", "Periodo Analizado"]

        # Cargar campos
        for etiqueta in campos_predeterminados:
            self.agregar_campo_dato(etiqueta, self.datos_generales.get(etiqueta, ""))
        for etiqueta, valor in self.datos_generales.items():
             if etiqueta not in campos_predeterminados:
                 self.agregar_campo_dato(etiqueta, valor)

        # Botones
        frame_botones = ttk.Frame(main_frame)
        frame_botones.pack(fill=tk.X, pady=(10, 0))
        frame_botones.grid_columnconfigure((0, 1), weight=1)
        btn_agregar = ttk.Button(frame_botones, text="➕ Añadir Campo", command=self.agregar_campo_personalizado)
        btn_agregar.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        btn_guardar = ttk.Button(frame_botones, text="💾 Guardar Datos", command=lambda: self.guardar_datos_generales(ventana), style="Accent.TButton")
        btn_guardar.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

    def agregar_campo_dato(self, etiqueta, valor_inicial=""):
        frame_campo = ttk.Frame(self.frame_datos)
        frame_campo.pack(pady=3, fill=tk.X)
        frame_campo.grid_columnconfigure(1, weight=1)
        
        btn_del = ttk.Button(frame_campo, text="🗑️", width=3, command=lambda f=frame_campo, k=etiqueta: self.eliminar_campo_dato(f, k))
        btn_del.grid(row=0, column=0, padx=(0, 5))
        
        ttk.Label(frame_campo, text=f"{etiqueta}:", width=20, anchor="w").grid(row=0, column=1, padx=5, sticky="w")
        
        entrada = ttk.Entry(frame_campo, width=30)
        entrada.grid(row=0, column=2, sticky="ew")
        entrada.insert(0, valor_inicial)
        self.campos_generales[etiqueta] = entrada

    def eliminar_campo_dato(self, frame_widget, key):
        if key in self.campos_generales:
            del self.campos_generales[key]
            frame_widget.destroy()

    def agregar_campo_personalizado(self):
        nueva_ventana = tk.Toplevel(self)
        nueva_ventana.title("Nuevo Campo")
        nueva_ventana.geometry("300x150")
        nueva_ventana.transient(self)
        nueva_ventana.grab_set()
        frame = ttk.Frame(nueva_ventana, padding="10")
        frame.pack(expand=True, fill="both")
        ttk.Label(frame, text="Nombre del nuevo campo:").pack(pady=5)
        campo_nombre_var = tk.StringVar()
        entry_nombre = ttk.Entry(frame, textvariable=campo_nombre_var, width=40)
        entry_nombre.pack(pady=5)
        entry_nombre.focus()
        ttk.Button(frame, text="Agregar", command=lambda: self.agregar_y_cerrar(campo_nombre_var.get(), nueva_ventana)).pack(pady=10)
        entry_nombre.bind("<Return>", lambda event: self.agregar_y_cerrar(campo_nombre_var.get(), nueva_ventana))

    def agregar_y_cerrar(self, etiqueta, ventana):
        etiqueta = etiqueta.strip()
        if etiqueta:
            if etiqueta in self.campos_generales:
                messagebox.showwarning("Duplicado", f"El campo '{etiqueta}' ya existe.")
            else:
                self.agregar_campo_dato(etiqueta)
                ventana.destroy()
        else:
            messagebox.showerror("Vacío", "El nombre no puede estar vacío.")

    def guardar_datos_generales(self, ventana):
        self.datos_generales = {k: v.get().strip() for k, v in self.campos_generales.items() if v.get().strip()}
        self.logger.info(f"Datos generales actualizados: {self.datos_generales}")
        ventana.destroy()

    def exportar_informe(self):
        if self.df is None:
            messagebox.showerror("Error", "Primero carga un archivo Excel.")
            return

        nombre_informe = self.nombre_informe.get().strip().replace(" ", "_")
        if not nombre_informe:
            base_excel = os.path.basename(self.archivo_path.get())
            nombre_sin_ext = os.path.splitext(base_excel)[0]
            nombre_informe = f"Informe_{nombre_sin_ext}"
            self.nombre_informe.set(nombre_informe)

        self.boton_exportar.config(state=tk.DISABLED, text="⚙️ Generando Informe...")
        self.update_idletasks()

        try:
            self.logger.info(f"--- Iniciando generación del informe: {nombre_informe} ---")

            # 1. Generar HTML (report_generator ahora maneja si faltan mapas)
            base_dir = generar_informe_html(
                self.df,
                nombre_informe=nombre_informe,
                incluir_membrete=self.incluir_logo.get(),
                logo_path=LOGO_PATH,
                pdf_financiero_path=self.pdf_path.get() if self.pdf_path.get() else None,
                nombres_asignados=self.nombres_asignados,
                datos_generales=self.datos_generales
            )

            # 2. Generar JSON
            json_path = os.path.join(base_dir, "data", "call_data.js")
            generar_datos_llamadas_json(self.df, json_path, nombres_asignados=self.nombres_asignados)

            # 3. Generar Gráficos (PNG)
            graphics_dir = os.path.join(base_dir, "graphics")
            os.makedirs(graphics_dir, exist_ok=True)
            
            # Filtros seguros por si faltan tipos de llamada
            if "tipo_llamada" in self.df.columns:
                df_ent = self.df[self.df["tipo_llamada"] == "entrante"]
                df_sal = self.df[self.df["tipo_llamada"] == "saliente"]
                
                if not df_ent.empty:
                    generar_grafico_top_llamadas(df_ent, "originador", "Top Llamadas Recibidas", os.path.join(graphics_dir, "top_llamadas_recibidas.png"))
                if not df_sal.empty:
                    generar_grafico_top_llamadas(df_sal, "receptor", "Top Llamadas Realizadas", os.path.join(graphics_dir, "top_llamadas_realizadas.png"))
            
            generar_grafico_horario_llamadas(self.df, os.path.join(graphics_dir, "grafico_horario_llamadas.png"))

            # 4. Mapas ya se generaron dentro de generar_informe_html si había coords

            self.logger.info("✅ Informe generado localmente.")

            # 5. FTP
            if self.subir_ftp.get():
                self.logger.info("Subiendo a FTP...")
                self.boton_exportar.config(text="📡 Subiendo a FTP...")
                self.update_idletasks()
                success = subir_archivo_ftp(
                    ftp_host=FTP_HOST,
                    ftp_user=FTP_USER,
                    ftp_pass=FTP_PASS,
                    carpeta_local=base_dir,
                    carpeta_remota=nombre_informe
                )
                if success:
                    url = f"https://{FTP_HOST}/{nombre_informe}/reports/informe_llamadas.html"
                    self.logger.info(f"✅ Subido: {url}")
                    self.mostrar_url_copiable(url)
                else:
                    self.logger.error("❌ Falló la subida FTP.")
                    messagebox.showerror("Error FTP", "No se pudo subir el informe.")
            else:
                report_file_path = os.path.join(base_dir, 'reports', 'informe_llamadas.html')
                messagebox.showinfo("Éxito", f"Informe generado en:\n{report_file_path}")
                try:
                    os.startfile(report_file_path)
                except:
                    pass

        except Exception as e:
            self.logger.error(f"❌ Error grave: {e}", exc_info=True)
            messagebox.showerror("Error Crítico", f"Ocurrió un error:\n{e}")
        finally:
            self.boton_exportar.config(state=tk.NORMAL, text="💾 Generar y Exportar Informe")

    def mostrar_url_copiable(self, url):
        ventana_url = tk.Toplevel(self)
        ventana_url.title("✅ Subida Exitosa")
        ventana_url.geometry("600x120")
        ventana_url.transient(self)
        ventana_url.grab_set()
        frame = ttk.Frame(ventana_url, padding="10")
        frame.pack(expand=True, fill="both")
        ttk.Label(frame, text="Informe subido. URL:").pack(pady=5)
        entry_url = ttk.Entry(frame, width=80)
        entry_url.insert(0, url)
        entry_url.configure(state="readonly")
        entry_url.pack(pady=5)
        entry_url.focus()
        entry_url.select_range(0, tk.END)
        def copiar():
            self.clipboard_clear()
            self.clipboard_append(url)
            btn.config(text="¡Copiado!")
        btn = ttk.Button(frame, text="Copiar URL", command=copiar)
        btn.pack(pady=5)

if __name__ == "__main__":
    app = CallAnalyzerGUI()
    app.mainloop()