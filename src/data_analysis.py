import pandas as pd
import os
import numpy as np

def cargar_datos_excel(file_path):
    """
    Carga datos desde un archivo Excel y verifica que las columnas esenciales estén presentes.
    """
    required_columns = ["originador", "receptor", "fecha_hora", "duracion", "latitud_n", "longitud_w"]

    if not os.path.exists(file_path):
        print(f"❌ Error: El archivo {file_path} no existe.")
        return None

    try:
        df = pd.read_excel(file_path)

        # Convertir nombres de columnas a minúsculas y eliminar espacios extra
        df.columns = df.columns.str.lower().str.strip()

        # Verificar si las columnas requeridas están presentes
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"⚠️ Error: Faltan columnas en el archivo Excel: {missing_columns}")
            return None

        # Convertir 'fecha_hora' a formato de fecha
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors='coerce')
        df.dropna(subset=["fecha_hora"], inplace=True)  # Eliminar filas sin fecha válida

        # Asegurar que 'duracion' sea numérico
        df["duracion"] = pd.to_numeric(df["duracion"], errors='coerce').fillna(0).astype(int)

        # Manejo de coordenadas (reparación de errores en valores numéricos)
        def corregir_coordenadas(valor):
            if pd.isna(valor) or valor == "" or valor == "?":
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

        print("✅ Archivo Excel cargado correctamente.")
        return df

    except Exception as e:
        print(f"❌ Error al cargar el archivo Excel: {e}")
        return None