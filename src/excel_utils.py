import pandas as pd
import os
import numpy as np

def cargar_excel_crudo(file_path):
    """
    Lee el Excel y devuelve un DataFrame unido (entrantes + salientes) 
    SIN validar nombres de columnas todavía.
    """
    if not os.path.exists(file_path):
        return None, "El archivo no existe."

    try:
        xl = pd.ExcelFile(file_path)
        hojas = {h.lower().strip(): h for h in xl.sheet_names}
        
        df_list = []
        
        # Buscar variantes de nombres de hojas
        found_sheets = False
        for key, real_name in hojas.items():
            if "entrant" in key or "incoming" in key: # Coincide con entrante, entrantes, incoming...
                try:
                    temp = pd.read_excel(file_path, sheet_name=real_name, dtype=str)
                    temp["tipo_llamada"] = "entrante"
                    df_list.append(temp)
                    found_sheets = True
                except Exception as e:
                    print(f"⚠️ Error leyendo hoja {real_name}: {e}")

            elif "salient" in key or "outgoing" in key: # Coincide con saliente, salientes, outgoing...
                try:
                    temp = pd.read_excel(file_path, sheet_name=real_name, dtype=str)
                    temp["tipo_llamada"] = "saliente"
                    df_list.append(temp)
                    found_sheets = True
                except Exception as e:
                    print(f"⚠️ Error leyendo hoja {real_name}: {e}")
        
        if not found_sheets or not df_list:
            # Si no hay hojas específicas, intentamos leer la primera hoja
            print("⚠️ No se detectaron hojas 'entrantes/salientes'. Leyendo primera hoja como genérica.")
            df = pd.read_excel(file_path, sheet_name=0, dtype=str)
            if "tipo_llamada" not in df.columns:
                df["tipo_llamada"] = "desconocido" # O intentar deducirlo
            return df, None

        df = pd.concat(df_list, ignore_index=True)
        return df, None

    except Exception as e:
        return None, str(e)

def procesar_dataframe_con_mapeo(df, mapping):
    """
    Recibe el DF crudo y un diccionario de mapeo {nombre_interno: nombre_excel}.
    Renombra las columnas y procesa los datos.
    """
    try:
        # 1. Renombrar columnas según lo que eligió el usuario
        # Invertimos el diccionario para el rename de pandas: {col_excel: col_interna}
        rename_dict = {v: k for k, v in mapping.items()}
        df = df.rename(columns=rename_dict)
        
        # 2. Filtrar solo las columnas que nos interesan (las que existen en el mapeo)
        cols_to_keep = list(mapping.keys()) + ["tipo_llamada"]
        # Aseguramos que solo pedimos las que realmente están tras el renombre
        cols_final = [c for c in cols_to_keep if c in df.columns]
        df = df[cols_final]

        # 3. Procesamiento de Fecha (CRÍTICO)
        # errors='coerce' transformará en NaT las fechas inválidas
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors='coerce', dayfirst=True)
        df.dropna(subset=["fecha_hora"], inplace=True)
        
        # 4. Procesamiento de Duración
        if "duracion" in df.columns:
            df["duracion"] = pd.to_numeric(df["duracion"], errors='coerce').fillna(0).astype(int)
        else:
            df["duracion"] = 0 # Valor por defecto

        # 5. Procesamiento de Coordenadas (OPCIONAL)
        def corregir_coordenadas(valor):
            if pd.isna(valor) or str(valor).strip() in ["", "?", "None", "nan"]:
                return np.nan
            try:
                valor = float(valor)
                if abs(valor) > 180: valor /= 10000 # Corrección formato común
                return valor
            except ValueError:
                return np.nan

        if "latitud_n" in df.columns:
            df["latitud_n"] = df["latitud_n"].apply(corregir_coordenadas)
        else:
            # Si no existe, no creamos la columna para que el resto del sistema sepa que no hay mapas
            pass 
            
        if "longitud_w" in df.columns:
            df["longitud_w"] = df["longitud_w"].apply(corregir_coordenadas)
        
        print(f"✅ Datos procesados. Filas resultantes: {len(df)}")
        return df

    except Exception as e:
        print(f"❌ Error procesando el DataFrame: {e}")
        return None