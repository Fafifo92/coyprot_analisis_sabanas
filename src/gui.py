# src/gui.py

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext # Importar scrolledtext
from ttkthemes import ThemedTk
import pandas as pd
import os
import shutil
import logging # Usar logging directamente para el logger
from utils import configurar_logs # Asegurar que configurar_logs se importa
from excel_utils import cargar_datos_excel
from report_generator import generar_informe_html, generar_datos_llamadas_json
from geo_utils import generar_mapa_interactivo, generar_mapa_calor
from graphics_utils import generar_grafico_top_llamadas, generar_grafico_horario_llamadas
from ftp_utils import subir_archivo_ftp

# --- Constantes ---
SRC_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(SRC_DIR)
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
STATIC_DIR = os.path.join(ROOT_DIR, "static")
LOGO_PATH = os.path.join(STATIC_DIR, "assets_img\\logo.png")
INFO_PATH = os.path.join(STATIC_DIR, "assets_img\\info.png")

# Credenciales FTP (Considera moverlas a un archivo de configuración o variables de entorno)
FTP_HOST = "plcoyprot.com"
FTP_USER = "plcoypro"
FTP_PASS = "181955Danilo?"

# --- Clase Principal de la GUI ---
class CallAnalyzerGUI(ThemedTk):
    def __init__(self):
        # Configuración inicial de la ventana con tema
        super().__init__(theme="adapta") # Puedes probar otros temas: "arc", "plastik", "clam", etc.
        self.title("📊 Analizador de Llamadas Pro")
        self.geometry("850x700") # Un poco más grande para mejor distribución
        self.minsize(700, 550) # Tamaño mínimo

        # --- Variables de Estado ---
        self.df = None
        self.nombres_asignados = {}
        self.datos_generales = {}
        self.incluir_logo = tk.BooleanVar(value=True) # Logo por defecto activado
        self.subir_ftp = tk.BooleanVar(value=False) # Subir a FTP desactivado por defecto
        self.archivo_path = tk.StringVar()
        self.pdf_path = tk.StringVar()
        self.nombre_informe = tk.StringVar(value="Informe_Llamadas") # Nombre por defecto

        # --- Configuración del Logging ---
        # Mover la creación del widget de log a create_widgets
        self.log_text_widget = None
        self.logger = configurar_logs() # Configura logs (archivo/consola)

        # --- Crear Widgets ---
        self.create_widgets()

        # --- Configurar Logger para GUI (después de crear el widget) ---
        if self.log_text_widget:
            self._configure_gui_logging()

        self.logger.info("Interfaz gráfica iniciada.")

    def _configure_gui_logging(self):
        """Configura el handler para enviar logs al widget Text."""
        # Handler para escribir logs al widget de texto
        class TextWidgetHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                # Asegurarse de que el widget esté habilitado para insertar
                self.text_widget.configure(state='normal')
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.configure(state='disabled')
                # Auto-scroll
                self.text_widget.see(tk.END)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        text_handler = TextWidgetHandler(self.log_text_widget)
        text_handler.setFormatter(formatter)
        text_handler.setLevel(logging.INFO) # Solo mostrar INFO y superior en GUI
        self.logger.addHandler(text_handler)
        # Remover handler de consola si ya existe uno para evitar duplicados (opcional)
        # self.logger.removeHandler(self.logger.handlers[1]) # Ajustar índice si es necesario


    def create_widgets(self):
        """Crea y organiza los widgets en la ventana principal usando grid."""

        main_frame = ttk.Frame(self, padding="10 10 10 10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Configurar grid para que se expanda
        main_frame.grid_rowconfigure(3, weight=1) # Fila del log se expande
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1) # Dos columnas principales

        # --- Sección de Carga de Archivos ---
        frame_cargar = ttk.LabelFrame(main_frame, text="📂 Archivos de Entrada", padding="10")
        frame_cargar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        frame_cargar.grid_columnconfigure(1, weight=1) # Entry se expande

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
        frame_opciones.grid_columnconfigure(0, weight=1) # Centrar botones

        self.boton_nombres = ttk.Button(frame_opciones, text="👤 Asignar Nombres a Números", command=self.asignar_nombres, state=tk.DISABLED)
        self.boton_nombres.grid(row=0, column=0, pady=5, padx=10, sticky="ew")

        self.boton_datos = ttk.Button(frame_opciones, text="📝 Añadir Datos Generales al Informe", command=self.abrir_editor_datos, state=tk.DISABLED)
        self.boton_datos.grid(row=1, column=0, pady=5, padx=10, sticky="ew")

        # --- Sección de Exportación ---
        frame_exportar = ttk.LabelFrame(main_frame, text="🚀 Exportar Informe", padding="10")
        frame_exportar.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        frame_exportar.grid_columnconfigure(1, weight=1) # Entry se expande

        ttk.Label(frame_exportar, text="Nombre del Informe:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry_nombre_informe = ttk.Entry(frame_exportar, textvariable=self.nombre_informe, width=30)
        entry_nombre_informe.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        frame_checks = ttk.Frame(frame_exportar)
        frame_checks.grid(row=1, column=0, columnspan=2, pady=5, sticky="w")
        chk_logo = ttk.Checkbutton(frame_checks, text="Incluir Membretes (Logo/Info)", variable=self.incluir_logo)
        chk_logo.pack(side=tk.LEFT, padx=5)
        chk_ftp = ttk.Checkbutton(frame_checks, text="Subir a FTP", variable=self.subir_ftp)
        chk_ftp.pack(side=tk.LEFT, padx=5)

        self.boton_exportar = ttk.Button(frame_exportar, text="💾 Generar y Exportar Informe", command=self.exportar_informe, style="Accent.TButton") # Estilo resaltado
        self.boton_exportar.grid(row=2, column=0, columnspan=2, pady=10, padx=5, ipady=5, sticky="ew")

        # Aplicar estilo Accent si el tema lo soporta
        style = ttk.Style()
        try:
            style.configure("Accent.TButton", font=('Helvetica', 10, 'bold')) # Puedes ajustar fuente y color
        except tk.TclError:
            self.logger.warning("El tema actual no soporta 'Accent.TButton'. Usando estilo por defecto.")


        # --- Sección de Logs ---
        frame_log = ttk.LabelFrame(main_frame, text="📋 Registro de Actividad", padding="10")
        frame_log.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        frame_log.grid_rowconfigure(0, weight=1)
        frame_log.grid_columnconfigure(0, weight=1)

        # Usar scrolledtext para incluir scrollbar automáticamente
        self.log_text_widget = scrolledtext.ScrolledText(frame_log, wrap=tk.WORD, height=10, state='disabled', font=('Consolas', 9)) # Fuente monoespaciada
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
            self.logger.info(f"Cargando archivo Excel: {os.path.basename(filepath)}...")
            # Mostrar feedback visual
            self.update_idletasks()
            self.df = cargar_datos_excel(filepath) # Esta función ya imprime/loggea errores
            if self.df is None or self.df.empty:
                messagebox.showerror("Error de Carga", "No se pudieron cargar los datos del archivo Excel. Revisa el registro de actividad.")
                self.boton_nombres.config(state=tk.DISABLED)
                self.boton_datos.config(state=tk.DISABLED)
            else:
                self.logger.info(f"✅ Archivo Excel cargado con éxito. {len(self.df)} filas encontradas.")
                messagebox.showinfo("Carga Exitosa", f"Archivo Excel '{os.path.basename(filepath)}' cargado.\n{len(self.df)} filas encontradas.")
                self.boton_nombres.config(state=tk.NORMAL)
                self.boton_datos.config(state=tk.NORMAL)

    def asignar_nombres(self):
        if self.df is None:
            messagebox.showwarning("Datos no cargados", "Primero carga un archivo Excel.")
            return

        # Obtener números únicos y ordenarlos
        numeros = sorted(list(set(self.df['originador'].astype(str).unique()) | set(self.df['receptor'].astype(str).unique())))

        ventana_nombres = tk.Toplevel(self)
        ventana_nombres.title("👤 Asignar Nombres a Números")
        ventana_nombres.geometry("550x550")
        ventana_nombres.transient(self) # Hacerla modal respecto a la ventana principal
        ventana_nombres.grab_set()

        # Frame principal con padding
        main_frame = ttk.Frame(ventana_nombres, padding="10")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="Asigna un nombre (alias) a cada número:", font="-weight bold").pack(pady=(0, 10))

        # --- Canvas y Scrollbar para la lista de números ---
        frame_canvas = ttk.Frame(main_frame)
        frame_canvas.pack(fill="both", expand=True)

        canvas = tk.Canvas(frame_canvas, borderwidth=0, background="#ffffff")
        scrollbar = ttk.Scrollbar(frame_canvas, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, padding="5") # Frame interior para los widgets

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        # --- Fin Canvas ---

        self.nombre_vars = {}
        # Usar grid dentro del scroll_frame para mejor alineación
        scroll_frame.grid_columnconfigure(1, weight=1) # Entry se expande
        for i, numero in enumerate(numeros):
            # Label para el número
            ttk.Label(scroll_frame, text=str(numero), width=20, anchor="w").grid(row=i, column=0, padx=5, pady=3, sticky="w")
            # Entry para el nombre
            nombre_var = tk.StringVar()
            # Recuperar nombre si ya fue asignado previamente
            nombre_var.set(self.nombres_asignados.get(str(numero), ""))
            self.nombre_vars[str(numero)] = nombre_var
            entry_nombre = ttk.Entry(scroll_frame, textvariable=nombre_var, width=35)
            entry_nombre.grid(row=i, column=1, padx=5, pady=3, sticky="ew")

        # Botón Guardar
        btn_guardar = ttk.Button(main_frame, text="Guardar Nombres", command=lambda: self.guardar_nombres(ventana_nombres))
        btn_guardar.pack(pady=10)

    def guardar_nombres(self, ventana):
        """Guarda los nombres asignados y cierra la ventana."""
        self.nombres_asignados = {num: var.get().strip() for num, var in self.nombre_vars.items() if var.get().strip()}
        self.logger.info(f"Nombres asignados actualizados: {len(self.nombres_asignados)} nombres guardados.")
        # Opcional: Mostrar resumen de nombres guardados
        # print(f"Nombres guardados: {self.nombres_asignados}")
        messagebox.showinfo("Nombres Guardados", f"Se han guardado {len(self.nombres_asignados)} nombres.", parent=ventana)
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

        # --- Frame con scroll para los campos ---
        frame_scrollable = ttk.Frame(main_frame)
        frame_scrollable.pack(fill=tk.BOTH, expand=True, pady=5)

        canvas = tk.Canvas(frame_scrollable, borderwidth=0, background="#ffffff")
        scrollbar = ttk.Scrollbar(frame_scrollable, orient="vertical", command=canvas.yview)
        self.frame_datos = ttk.Frame(canvas, padding="5") # Frame interno para los campos

        self.frame_datos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.frame_datos, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        # --- Fin Frame con scroll ---

        self.campos_generales = {}
        campos_predeterminados = ["Nombre Cliente", "Ciudad", "Teléfono Contacto", "Dirección", "Referencia Caso", "Periodo Analizado"]

        # Cargar campos existentes
        for etiqueta in campos_predeterminados:
            self.agregar_campo_dato(etiqueta, self.datos_generales.get(etiqueta, ""))
        # Cargar campos personalizados previamente guardados
        for etiqueta, valor in self.datos_generales.items():
             if etiqueta not in campos_predeterminados:
                 self.agregar_campo_dato(etiqueta, valor)


        # Botones de acción
        frame_botones = ttk.Frame(main_frame)
        frame_botones.pack(fill=tk.X, pady=(10, 0))
        frame_botones.grid_columnconfigure((0, 1), weight=1) # Distribuir botones

        btn_agregar = ttk.Button(frame_botones, text="➕ Añadir Campo", command=self.agregar_campo_personalizado)
        btn_agregar.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        btn_guardar = ttk.Button(frame_botones, text="💾 Guardar Datos", command=lambda: self.guardar_datos_generales(ventana), style="Accent.TButton")
        btn_guardar.grid(row=0, column=1, padx=5, pady=5, sticky="ew")


    def agregar_campo_dato(self, etiqueta, valor_inicial=""):
        """Agrega una fila de etiqueta y entrada al frame de datos."""
        frame_campo = ttk.Frame(self.frame_datos)
        frame_campo.pack(pady=3, fill=tk.X)
        frame_campo.grid_columnconfigure(1, weight=1) # Entry se expande

        # Eliminar campo (opcional)
        btn_del = ttk.Button(frame_campo, text="🗑️", width=3, command=lambda f=frame_campo, k=etiqueta: self.eliminar_campo_dato(f, k))
        btn_del.grid(row=0, column=0, padx=(0, 5))

        lbl = ttk.Label(frame_campo, text=f"{etiqueta}:", width=20, anchor="w")
        lbl.grid(row=0, column=1, padx=5, sticky="w")

        entrada = ttk.Entry(frame_campo, width=30)
        entrada.grid(row=0, column=2, sticky="ew")
        entrada.insert(0, valor_inicial) # Poner valor inicial
        self.campos_generales[etiqueta] = entrada


    def eliminar_campo_dato(self, frame_widget, key):
        """Elimina un campo de datos de la GUI y del diccionario."""
        if key in self.campos_generales:
            del self.campos_generales[key]
            frame_widget.destroy()
            self.logger.info(f"Campo '{key}' eliminado del editor.")


    def agregar_campo_personalizado(self):
        """Abre una pequeña ventana para pedir el nombre del nuevo campo."""
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
        entry_nombre.focus() # Poner foco en la entrada

        btn_agregar = ttk.Button(frame, text="Agregar Campo", command=lambda: self.agregar_y_cerrar(campo_nombre_var.get(), nueva_ventana))
        btn_agregar.pack(pady=10)

        # Permitir agregar con Enter
        entry_nombre.bind("<Return>", lambda event: self.agregar_y_cerrar(campo_nombre_var.get(), nueva_ventana))


    def agregar_y_cerrar(self, etiqueta, ventana):
        """Agrega el campo nuevo si es válido y cierra la ventana."""
        etiqueta = etiqueta.strip()
        if etiqueta:
            if etiqueta in self.campos_generales:
                messagebox.showwarning("Campo Duplicado", f"El campo '{etiqueta}' ya existe.", parent=ventana)
            else:
                self.agregar_campo_dato(etiqueta)
                ventana.destroy()
        else:
            messagebox.showerror("Campo Vacío", "El nombre del campo no puede estar vacío.", parent=ventana)


    def guardar_datos_generales(self, ventana):
        """Guarda los datos generales introducidos y cierra la ventana."""
        self.datos_generales = {
            campo: entrada.get().strip()
            for campo, entrada in self.campos_generales.items()
            if entrada.get().strip() # Solo guardar si tiene valor
        }
        self.logger.info(f"Datos generales actualizados: {self.datos_generales}")
        messagebox.showinfo("Datos Guardados", "Los datos generales del informe han sido guardados.", parent=ventana)
        ventana.destroy()


    def exportar_informe(self):
        """Genera y exporta el informe completo."""
        if self.df is None:
            messagebox.showerror("Error", "Primero carga un archivo Excel.")
            return

        nombre_informe = self.nombre_informe.get().strip().replace(" ", "_")
        if not nombre_informe:
            # Generar nombre por defecto si está vacío
            base_excel = os.path.basename(self.archivo_path.get())
            nombre_sin_ext = os.path.splitext(base_excel)[0]
            nombre_informe = f"Informe_{nombre_sin_ext}"
            self.nombre_informe.set(nombre_informe)
            # messagebox.showerror("Error", "Ingresa un nombre válido para el informe.")
            # return

        # --- Feedback Visual y Deshabilitar Botón ---
        self.boton_exportar.config(state=tk.DISABLED, text="⚙️ Generando Informe...")
        self.update_idletasks() # Forzar actualización de la GUI

        try:
            self.logger.info(f"--- Iniciando generación del informe: {nombre_informe} ---")

            # 1. Generar estructura de directorios y copiar PDF si existe
            self.logger.info("Creando estructura de directorios...")
            base_dir = self._preparar_directorio_salida(nombre_informe)
            if not base_dir: # Si hubo error al crear directorios
                 raise Exception("No se pudo crear el directorio de salida.")

            # 2. Generar informe HTML principal
            self.logger.info("Generando archivo HTML principal...")
            generar_informe_html(
                self.df,
                nombre_informe=nombre_informe,
                incluir_membrete=self.incluir_logo.get(),
                logo_path=LOGO_PATH, # Pasa siempre, la plantilla decide si usarlo
                pdf_financiero_path=self.pdf_path.get() if self.pdf_path.get() else None,
                nombres_asignados=self.nombres_asignados,
                datos_generales=self.datos_generales
            )

            # 3. Generar datos JSON para gráficos interactivos
            self.logger.info("Generando datos JSON para interactividad (call_data.js)...")
            json_path = os.path.join(base_dir, "data", "call_data.js")
            generar_datos_llamadas_json(self.df, json_path, nombres_asignados=self.nombres_asignados)

            # 4. Generar Gráficos (Imágenes PNG)
            self.logger.info("Generando gráficos estáticos (PNG)...")
            graphics_dir = os.path.join(base_dir, "graphics")
            os.makedirs(graphics_dir, exist_ok=True)
            generar_grafico_top_llamadas(self.df[self.df["tipo_llamada"] == "entrante"], "originador", "Top Llamadas Recibidas", os.path.join(graphics_dir, "top_llamadas_recibidas.png"))
            generar_grafico_top_llamadas(self.df[self.df["tipo_llamada"] == "saliente"], "receptor", "Top Llamadas Realizadas", os.path.join(graphics_dir, "top_llamadas_realizadas.png"))
            generar_grafico_horario_llamadas(self.df, os.path.join(graphics_dir, "grafico_horario_llamadas.png"))

            # 5. Generar Mapas (HTML)
            self.logger.info("Generando mapas interactivos (HTML)...")
            maps_dir = os.path.join(base_dir, "maps")
            os.makedirs(maps_dir, exist_ok=True)
            generar_mapa_interactivo(self.df, os.path.join(maps_dir, "mapa_general.html"))
            generar_mapa_calor(self.df, os.path.join(maps_dir, "mapa_calor.html"))

            # 6. Copiar archivos estáticos (JS, CSS, logos si aplica)
            self.logger.info("Copiando archivos estáticos necesarios (JS, imágenes)...")
            self._copiar_archivos_estaticos(base_dir)

            self.logger.info("✅ Informe generado localmente con éxito.")

            # 7. Subir a FTP si está seleccionado
            if self.subir_ftp.get():
                self.logger.info("Intentando subir informe completo al servidor FTP...")
                self.boton_exportar.config(text="📡 Subiendo a FTP...")
                self.update_idletasks()

                success = subir_archivo_ftp(
                    ftp_host=FTP_HOST,
                    ftp_user=FTP_USER,
                    ftp_pass=FTP_PASS,
                    carpeta_local=base_dir,
                    carpeta_remota=nombre_informe # Usar el nombre del informe como carpeta remota
                )
                if success:
                    url = f"https://{FTP_HOST}/{nombre_informe}/reports/informe_llamadas.html"
                    self.logger.info(f"✅ Informe subido correctamente a FTP. URL: {url}")
                    self.mostrar_url_copiable(url)
                else:
                    self.logger.error("❌ Error al subir el informe al FTP.")
                    messagebox.showerror("Error de FTP", "No se pudo subir el informe al servidor FTP. Revisa las credenciales y la conexión.")
            else:
                 # Si no se sube a FTP, solo mostrar mensaje local
                 report_file_path = os.path.join(base_dir, 'reports', 'informe_llamadas.html')
                 messagebox.showinfo("Éxito", f"Informe generado localmente en:\n{base_dir}\n\nPuedes abrir el archivo:\n{report_file_path}")
                 # Intentar abrir el archivo HTML generado
                 try:
                     os.startfile(report_file_path)
                 except AttributeError: # os.startfile no existe en algunos sistemas (Linux)
                     import webbrowser
                     webbrowser.open(f"file://{os.path.abspath(report_file_path)}")
                 except Exception as open_err:
                     self.logger.warning(f"No se pudo abrir automáticamente el informe: {open_err}")


        except Exception as e:
            self.logger.error(f"❌ Ocurrió un error grave durante la generación del informe: {e}", exc_info=True) # Log con traceback
            messagebox.showerror("Error Crítico", f"Error al generar el informe:\n{e}\n\nConsulta el registro para más detalles.")
        finally:
            # --- Rehabilitar Botón ---
            self.boton_exportar.config(state=tk.NORMAL, text="💾 Generar y Exportar Informe")


    def _preparar_directorio_salida(self, nombre_informe):
        """Crea la estructura de directorios para el informe."""
        base_output = os.path.join(ROOT_DIR, "output", nombre_informe)
        dirs_a_crear = [
            os.path.join(base_output, "reports"),
            os.path.join(base_output, "maps"),
            os.path.join(base_output, "graphics"),
            os.path.join(base_output, "data"),
            os.path.join(base_output, "static", "assets_js"), # Subcarpeta para JS
            os.path.join(base_output, "static", "assets_img") # Subcarpeta para imágenes
        ]
        try:
            for d in dirs_a_crear:
                os.makedirs(d, exist_ok=True)

            # Copiar PDF financiero si existe y es válido
            pdf_origen = self.pdf_path.get()
            if pdf_origen and os.path.exists(pdf_origen):
                 pdf_dest = os.path.join(base_output, "data", "reporte_financiero.pdf")
                 shutil.copy2(pdf_origen, pdf_dest) # copy2 preserva metadatos
                 self.logger.info("PDF financiero copiado a la carpeta 'data'.")

            return base_output
        except OSError as e:
            self.logger.error(f"Error creando directorios o copiando PDF: {e}")
            messagebox.showerror("Error de Directorio", f"No se pudo crear la estructura de carpetas para el informe:\n{e}")
            return None


    def _copiar_archivos_estaticos(self, base_dir):
        """Copia los archivos JS, CSS e imágenes necesarios al directorio static del informe."""
        static_dest = os.path.join(base_dir, "static")
        js_dest = os.path.join(static_dest, "assets_js")
        img_dest = os.path.join(static_dest, "assets_img") # Directorio para imágenes

        archivos_a_copiar = {
            os.path.join(STATIC_DIR, "assets_js", "interactive_maps.js"): js_dest,
            os.path.join(STATIC_DIR, "assets_js", "interactive_charts.js"): js_dest,
        }

        # Copiar logos si la opción está activada y los archivos existen
        if self.incluir_logo.get():
            if os.path.exists(LOGO_PATH):
                archivos_a_copiar[LOGO_PATH] = img_dest # Copiar a assets_img
            else:
                self.logger.warning(f"Archivo de logo no encontrado en {LOGO_PATH}")
            if os.path.exists(INFO_PATH):
                archivos_a_copiar[INFO_PATH] = img_dest # Copiar a assets_img
            else:
                self.logger.warning(f"Archivo de info no encontrado en {INFO_PATH}")

        for src, dest_folder in archivos_a_copiar.items():
            try:
                if os.path.exists(src):
                    # Crear carpeta destino si no existe (redundante por makedirs, pero seguro)
                    os.makedirs(dest_folder, exist_ok=True)
                    shutil.copy2(src, os.path.join(dest_folder, os.path.basename(src)))
                else:
                     self.logger.warning(f"Archivo estático no encontrado, no se copiará: {src}")
            except Exception as e:
                self.logger.error(f"Error al copiar archivo estático '{os.path.basename(src)}': {e}")
                messagebox.showwarning("Error Copiando Archivos", f"No se pudo copiar el archivo: {os.path.basename(src)}")


    def mostrar_url_copiable(self, url):
        """Muestra una ventana simple para copiar la URL del informe subido."""
        ventana_url = tk.Toplevel(self)
        ventana_url.title("✅ Informe Subido a FTP")
        ventana_url.geometry("600x120") # Más ancha para la URL
        ventana_url.transient(self)
        ventana_url.grab_set()

        frame = ttk.Frame(ventana_url, padding="10")
        frame.pack(expand=True, fill="both")

        ttk.Label(frame, text="Informe subido con éxito. Puedes copiar la URL:").pack(pady=5)

        entry_url = ttk.Entry(frame, width=80)
        entry_url.insert(0, url)
        entry_url.configure(state="readonly") # Hacerla de solo lectura
        entry_url.pack(pady=5, padx=5)

        # Seleccionar automáticamente la URL al abrir
        entry_url.focus()
        entry_url.select_range(0, tk.END)
        entry_url.icursor(tk.END)

        def copiar_url():
            self.clipboard_clear()
            self.clipboard_append(url)
            self.logger.info(f"URL copiada al portapapeles: {url}")
            # Cambiar texto del botón brevemente
            btn_copiar.config(text="¡Copiado!")
            ventana_url.after(1500, lambda: btn_copiar.config(text="Copiar URL")) # Volver al texto original

        btn_copiar = ttk.Button(frame, text="Copiar URL", command=copiar_url)
        btn_copiar.pack(pady=10)


# --- Punto de Entrada ---
if __name__ == "__main__":
    # Configuración inicial de logs ANTES de crear la GUI
    # para capturar cualquier error temprano.
    # logger = configurar_logs() # Ya se llama en __init__ de la clase

    app = CallAnalyzerGUI()
    app.mainloop()