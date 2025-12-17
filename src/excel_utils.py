import pandas as pd
import os
import numpy as np
# Importamos la lógica de limpieza que acabamos de definir
from phone_utils import normalizar_numero_colombia

def cargar_excel_crudo(file_path):
    """
    Lee el Excel buscando hojas que contengan 'entrantes' o 'salientes'.
    Si las encuentra, agrega una columna 'tipo_llamada'.
    Si no, lee la primera hoja como genérica.
    Devuelve un DataFrame unido sin procesar (raw).
    """
    if not os.path.exists(file_path):
        return None, "El archivo no existe."

    try:
        xl = pd.ExcelFile(file_path)
        # Normalizamos nombres de hojas a minúsculas para facilitar la búsqueda
        hojas = {h.lower().strip(): h for h in xl.sheet_names}
        
        df_list = []
        found_sheets = False
        
        # Buscar variantes de nombres de hojas
        for key, real_name in hojas.items():
            # Hojas de Entrantes
            if "entrant" in key or "incoming" in key: 
                try:
                    # Leemos todo como string para no perder ceros a la izquierda
                    temp = pd.read_excel(file_path, sheet_name=real_name, dtype=str)
                    temp["tipo_llamada"] = "entrante"
                    df_list.append(temp)
                    found_sheets = True
                except Exception as e:
                    print(f"⚠️ Error leyendo hoja {real_name}: {e}")

            # Hojas de Salientes
            elif "salient" in key or "outgoing" in key: 
                try:
                    temp = pd.read_excel(file_path, sheet_name=real_name, dtype=str)
                    temp["tipo_llamada"] = "saliente"
                    df_list.append(temp)
                    found_sheets = True
                except Exception as e:
                    print(f"⚠️ Error leyendo hoja {real_name}: {e}")
        
        # Si no encontró hojas específicas, lee la primera
        if not found_sheets or not df_list:
            print("⚠️ No se detectaron hojas específicas (entrantes/salientes). Leyendo primera hoja como genérica.")
            df = pd.read_excel(file_path, sheet_name=0, dtype=str)
            # Si no existe la columna tipo, la marcamos como desconocido
            if "tipo_llamada" not in df.columns:
                df["tipo_llamada"] = "desconocido"
            return df, None

        # Unir todas las hojas encontradas en un solo DataFrame
        df = pd.concat(df_list, ignore_index=True)
        return df, None

    except Exception as e:
        return None, str(e)

def procesar_dataframe_con_mapeo(df, mapping):
    """
    Aplica el mapeo de columnas seleccionado por el usuario y
    REALIZA LA LIMPIEZA PROFUNDA DE DATOS.
    """
    try:
        # 1. Renombrar columnas según el mapeo del usuario
        # El mapping viene como {nombre_interno: nombre_excel}
        rename_dict = {v: k for k, v in mapping.items()}
        df = df.rename(columns=rename_dict)
        
        # 2. Filtrar solo las columnas mapeadas + tipo_llamada
        cols_to_keep = list(mapping.keys()) + ["tipo_llamada"]
        # Aseguramos que solo pedimos las que realmente existen tras el renombre
        cols_final = [c for c in cols_to_keep if c in df.columns]
        df = df[cols_final]

        # --- 3. NORMALIZACIÓN DE NÚMEROS (LA MEJORA CLAVE) ---
        # Esto unifica 57300... y 300... en un solo formato
        print("🧹 Limpiando y normalizando números telefónicos...")
        
        if "originador" in df.columns:
            df["originador"] = df["originador"].apply(normalizar_numero_colombia)
        
        if "receptor" in df.columns:
            df["receptor"] = df["receptor"].apply(normalizar_numero_colombia)
        
        # 4. Procesamiento de Fecha
        # errors='coerce' convierte errores en NaT (Not a Time), luego eliminamos esas filas
        if "fecha_hora" in df.columns:
            df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors='coerce', dayfirst=True)
            df.dropna(subset=["fecha_hora"], inplace=True)
        
        # 5. Procesamiento de Duración
        if "duracion" in df.columns:
            df["duracion"] = pd.to_numeric(df["duracion"], errors='coerce').fillna(0).astype(int)
        else:
            df["duracion"] = 0 # Valor por defecto si no existe

        # 6. Procesamiento de Coordenadas (Limpieza de formato)
        def corregir_coordenadas(valor):
            # Filtros básicos de nulos
            if pd.isna(valor) or str(valor).strip() in ["", "?", "None", "nan", "0"]:
                return np.nan
            try:
                valor = float(valor)
                # Corrección formato común en CDRs: 47286 -> 4.7286 (Latitud Colombia aprox 4.0)
                # Si el valor absoluto es mayor a 180 (límite geográfico), asumimos falta de punto decimal
                if abs(valor) > 180: 
                    valor /= 10000 
                return valor
            except ValueError:
                return np.nan

        if "latitud_n" in df.columns:
            df["latitud_n"] = df["latitud_n"].apply(corregir_coordenadas)
        
        if "longitud_w" in df.columns:
            df["longitud_w"] = df["longitud_w"].apply(corregir_coordenadas)
        
        print(f"✅ Datos procesados. Total registros limpios: {len(df)}")
        return df

    except Exception as e:
        print(f"❌ Error procesando el DataFrame: {e}")
        return None