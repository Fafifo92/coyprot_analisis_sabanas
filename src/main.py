import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os

# Importamos tu clase del otro archivo
from column_mapper import ColumnMapperDialog

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Análisis de CDR")
        self.root.geometry("800x600")
        
        self.df = None # Aquí vivirá el DataFrame cargado
        
        self.create_ui()
        
    def create_ui(self):
        # Frame superior para controles
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill="x")
        
        btn_load = ttk.Button(control_frame, text="📂 Cargar Excel/CSV", command=self.cargar_archivo)
        btn_load.pack(side="left", padx=5)
        
        self.lbl_status = ttk.Label(control_frame, text="Estado: Esperando archivo...", foreground="gray")
        self.lbl_status.pack(side="left", padx=10)
        
        # Frame principal para mostrar datos (Vista previa)
        self.tree_frame = ttk.Frame(self.root, padding=10)
        self.tree_frame.pack(fill="both", expand=True)
        
        # Scrollbars y Treeview
        self.tree_scroll = ttk.Scrollbar(self.tree_frame)
        self.tree_scroll.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(self.tree_frame, yscrollcommand=self.tree_scroll.set, show="headings")
        self.tree.pack(fill="both", expand=True)
        self.tree_scroll.config(command=self.tree.yview)

    def cargar_archivo(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Archivos de Datos", "*.xlsx *.xls *.csv")]
        )
        
        if not filepath:
            return

        try:
            # 1. Lectura preliminar
            self.lbl_status.config(text="Leyendo archivo...", foreground="blue")
            self.root.update()
            
            if filepath.endswith('.csv'):
                df_temp = pd.read_csv(filepath)
            else:
                df_temp = pd.read_excel(filepath)
            
            # 2. INVOCAR EL MAPEO (Aquí sucede la magia)
            # Pasamos la lista de columnas tal como vienen en el Excel
            dialogo = ColumnMapperDialog(self.root, df_temp.columns.tolist())
            self.root.wait_window(dialogo) # Detiene el código hasta que se cierre el dialogo
            
            # 3. Verificar resultado
            if dialogo.result is None:
                self.lbl_status.config(text="Carga cancelada por el usuario.", foreground="red")
                return

            # 4. Aplicar el renombrado
            # El dialogo devuelve: {'originador': 'Columna A'}
            # Pandas necesita: {'Columna A': 'originador'}
            mapeo_renombre = {v: k for k, v in dialogo.result.items()}
            
            df_temp.rename(columns=mapeo_renombre, inplace=True)
            
            # 5. Guardar DF procesado
            self.df = df_temp
            
            # 6. Actualizar UI
            self.mostrar_datos()
            self.lbl_status.config(text=f"Archivo cargado: {os.path.basename(filepath)} ({len(self.df)} registros)", foreground="green")
            messagebox.showinfo("Éxito", "Las columnas se han unificado correctamente.\nEl sistema ahora reconoce tus datos.")

        except Exception as e:
            self.lbl_status.config(text="Error en la carga", foreground="red")
            messagebox.showerror("Error Crítico", f"No se pudo procesar el archivo:\n{e}")

    def mostrar_datos(self):
        """Muestra las primeras 50 filas en la tabla para verificar"""
        self.tree.delete(*self.tree.get_children())
        
        # Definir columnas del Treeview basadas en el DF final
        cols = list(self.df.columns)
        self.tree["columns"] = cols
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, stretch=True)
            
        # Insertar datos (solo primeros 50 para velocidad)
        for _, row in self.df.head(50).iterrows():
            self.tree.insert("", "end", values=list(row))

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()