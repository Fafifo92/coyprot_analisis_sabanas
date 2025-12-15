import pandas as pd
import os
import numpy as np

def cargar_datos_excel(file_path):
    """
    Carga datos desde un archivo Excel y busca específicamente las hojas 'salientes' y 'entrantes'.
    Si las encuentra, las une en un solo DataFrame agregando una columna 'tipo_llamada'.
    """

    # Verificar si el archivo existe
    if not os.path.exists(file_path):
        print(f"❌ Error: El archivo {file_path} no existe.")
        return None

    try:
        # Leer todas las hojas del archivo
        hojas = pd.ExcelFile(file_path).sheet_names
        hojas_nombres = {nombre.lower().strip(): nombre for nombre in hojas}  # Normaliza nombres de hojas

        # Buscar hojas 'entrantes' y 'salientes'
        hoja_entrantes = hojas_nombres.get("entrantes")
        hoja_salientes = hojas_nombres.get("salientes")

        if not hoja_entrantes and not hoja_salientes:
            print("⚠️ Error: No se encontraron hojas llamadas 'entrantes' ni 'salientes'.")
            return None

        # Cargar los DataFrames correspondientes
        df_entrantes = pd.DataFrame()
        df_salientes = pd.DataFrame()

        if hoja_entrantes:
            df_entrantes = pd.read_excel(file_path, sheet_name=hoja_entrantes, dtype=str)
            df_entrantes["tipo_llamada"] = "entrante"

        if hoja_salientes:
            df_salientes = pd.read_excel(file_path, sheet_name=hoja_salientes, dtype=str)
            df_salientes["tipo_llamada"] = "saliente"

        # Unir ambas tablas en un solo DataFrame
        df = pd.concat([df_entrantes, df_salientes], ignore_index=True)

        # Convertir nombres de columnas a minúsculas y eliminar espacios extra
        df.columns = df.columns.str.lower().str.strip()

        # Columnas requeridas
        required_columns = ["originador", "receptor", "fecha_hora", "duracion", "latitud_n", "longitud_w"]

        # Verificar si faltan columnas
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"⚠️ Error: Faltan columnas en el archivo Excel: {missing_columns}")
            return None

        # ✅ Corrección: Convertir 'fecha_hora' a formato de fecha con dayfirst=True
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors='coerce', dayfirst=True)

        # Contar fechas inválidas
        fechas_invalidas = df["fecha_hora"].isna().sum()
        if fechas_invalidas > 0:
            print(f"⚠️ Advertencia: {fechas_invalidas} registros tienen fechas inválidas y se marcarán como 'NaT'.")

        # Asegurar que 'duracion' sea numérico
        df["duracion"] = pd.to_numeric(df["duracion"], errors='coerce').fillna(0).astype(int)

        # Manejo de coordenadas (reparación de errores en valores numéricos)
        def corregir_coordenadas(valor):
            if pd.isna(valor) or valor in ["", "?", "None"]:
                return np.nan
            try:
                valor = float(valor)
                if abs(valor) > 180:  # Detectar errores de formato (ejemplo: 47286 en lugar de 4.7286)
                    valor /= 10000
                return valor
            except ValueError:
                return np.nan

        df["latitud_n"] = df["latitud_n"].apply(corregir_coordenadas)
        df["longitud_w"] = df["longitud_w"].apply(corregir_coordenadas)

        # Mostrar cuántos registros se cargaron
        print(f"✅ Archivo Excel cargado correctamente. Total filas: {len(df)}")
        return df

    except Exception as e:
        print(f"❌ Error al cargar el archivo Excel: {e}")
        return None

if __name__ == "__main__":
    archivo_excel = "ruta_al_archivo.xlsx"  # Cambiar por la ruta real
    df = cargar_datos_excel(archivo_excel)
    
    if df is not None:
        print("🔍 Primeras filas del DataFrame:")
        print(df.head())