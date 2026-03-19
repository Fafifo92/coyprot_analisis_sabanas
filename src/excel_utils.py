import pandas as pd
import os
import numpy as np
# Importamos la lógica de limpieza
from phone_utils import normalizar_numero_colombia

def robust_date_parser(value):
    """
    Motor inteligente para detectar fechas. 
    Maneja el formato serial de Excel y formatos de texto variados.
    """
    if pd.isna(value) or str(value).strip() in ["", "nan", "None", "NaT"]:
        return pd.NaT
    
    value_str = str(value).strip()

    # Caso A: Si es un número (formato serial de Excel)
    if value_str.replace('.', '', 1).isdigit():
        try:
            num_val = float(value_str)
            if 32874 < num_val < 51138: 
                return pd.to_datetime(num_val, unit='D', origin='1899-12-30').round('S')
        except:
            pass

    # Caso B: Probar formatos de texto específicos
    formatos = [
        "%Y/%m/%d %H:%M:%S",  # 2025/10/08 12:04:47 (EL TUYO)
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y%m%d %H%M%S"
    ]
    
    for fmt in formatos:
        try:
            return pd.to_datetime(value_str, format=fmt)
        except:
            continue
            
    # Caso C: Intento final automático
    try:
        return pd.to_datetime(value_str, errors='coerce', dayfirst=False)
    except:
        return pd.NaT

def cargar_excel_crudo(file_path):
    """
    Lee el Excel buscando hojas de 'entrantes', 'salientes' Y 'DATOS'.
    Elimina filas vacías y normaliza columnas basándose en tu estructura.
    """
    if not os.path.exists(file_path):
        return None, "El archivo no existe."

    try:
        xl = pd.ExcelFile(file_path)
        hojas = {h.lower().strip(): h for h in xl.sheet_names}
        
        df_list = []
        found_sheets = False
        
        for key, real_name in hojas.items():
            
            # --- 1. HOJA DE DATOS (LA QUE TIENE COORDENADAS PROPIAS) ---
            if "dato" in key: 
                try:
                    print(f"📡 Procesando hoja de DATOS: {real_name}")
                    # Leemos todo como string
                    temp = pd.read_excel(file_path, sheet_name=real_name, dtype=str)
                    
                    # 1. ELIMINAR FILAS VACÍAS
                    temp.dropna(how='all', inplace=True)
                    
                    # 2. MAPEO EXACTO BASADO EN TU ESTRUCTURA REAL
                    # Traduce tus columnas de Excel a las columnas internas del sistema
                    rename_map = {
                        "numero": "originador",
                        "fecha_trafico": "fecha_hora",       # Tu columna -> Sistema
                        "tipo_cdr": "tipo_llamada",          # Tu columna -> Sistema
                        "latitud": "latitud_n",              # CORRECCIÓN CLAVE
                        "longitud": "longitud_w",            # CORRECCIÓN CLAVE
                        "cell_identity_decimal": "cell_identity_decimal",
                        "nombre_celda": "nombre_celda",
                        "location_area_code_decimal": "lac"
                    }
                    
                    # Renombrar columnas insensible a mayúsculas/minúsculas
                    cols_actuales = {c.lower().strip(): c for c in temp.columns}
                    nuevo_mapa = {}
                    for k_deseada, v_destino in rename_map.items():
                        if k_deseada in cols_actuales:
                            nuevo_mapa[cols_actuales[k_deseada]] = v_destino
                            
                    temp.rename(columns=nuevo_mapa, inplace=True)
                    
                    # Asegurar tipo llamada tenga valor si está vacío
                    if "tipo_llamada" not in temp.columns:
                        temp["tipo_llamada"] = "DATOS"
                    else:
                        # Rellenar nulos en tipo_llamada con "DATOS" por si acaso
                        temp["tipo_llamada"] = temp["tipo_llamada"].fillna("DATOS")
                    
                    # Rellenar receptor para que no falle la lógica general
                    if "receptor" not in temp.columns:
                        temp["receptor"] = "INTERNET/DATOS"
                        
                    # Limpiar nombres de columnas restantes
                    temp.columns = temp.columns.str.lower().str.strip()
                        
                    df_list.append(temp)
                    found_sheets = True
                except Exception as e:
                    print(f"⚠️ Error leyendo hoja de datos {real_name}: {e}")

            # --- 2. Hojas de Entrantes ---
            elif "entrant" in key or "incoming" in key:
                try:
                    temp = pd.read_excel(file_path, sheet_name=real_name, dtype=str)
                    temp.dropna(how='all', inplace=True)
                    temp.columns = temp.columns.str.lower().str.strip()
                    if "fecha_hora_inicio_llamada" in temp.columns and "fecha_hora" not in temp.columns:
                        temp.rename(columns={"fecha_hora_inicio_llamada": "fecha_hora"}, inplace=True)
                    temp["tipo_llamada"] = "entrante"
                    df_list.append(temp)
                    found_sheets = True
                except Exception as e:
                    print(f"⚠️ Error leyendo hoja {real_name}: {e}")

            # --- 3. Hojas de Salientes ---
            elif "salient" in key or "outgoing" in key:
                try:
                    temp = pd.read_excel(file_path, sheet_name=real_name, dtype=str)
                    temp.dropna(how='all', inplace=True)
                    temp.columns = temp.columns.str.lower().str.strip()
                    if "fecha_hora_inicio_llamada" in temp.columns and "fecha_hora" not in temp.columns:
                        temp.rename(columns={"fecha_hora_inicio_llamada": "fecha_hora"}, inplace=True)
                    temp["tipo_llamada"] = "saliente"
                    df_list.append(temp)
                    found_sheets = True
                except Exception as e:
                    print(f"⚠️ Error leyendo hoja {real_name}: {e}")
        
        if not found_sheets or not df_list:
            print("⚠️ No se detectaron hojas específicas. Leyendo primera hoja como genérica.")
            df = pd.read_excel(file_path, sheet_name=0, dtype=str)
            df.dropna(how='all', inplace=True)
            df.columns = df.columns.str.lower().str.strip()
            if "tipo_llamada" not in df.columns:
                df["tipo_llamada"] = "desconocido"
            return df, None

        # Unir
        df = pd.concat(df_list, ignore_index=True, sort=False)
        
        # --- BLINDAJE DUPLICADOS (EVITA EL ERROR TRUTH VALUE) ---
        df = df.loc[:, ~df.columns.duplicated()]
        
        return df, None

    except Exception as e:
        return None, str(e)

def procesar_dataframe_con_mapeo(df, mapping):
    """
    Limpieza profunda de datos.
    """
    try:
        # Limpieza inicial de duplicados por seguridad
        df = df.loc[:, ~df.columns.duplicated()]

        if mapping:
            rename_dict = {v: k for k, v in mapping.items()}
            rename_dict = {k: v for k, v in rename_dict.items() if k in df.columns}
            df = df.rename(columns=rename_dict)
        
        df = df.loc[:, ~df.columns.duplicated()]

        required = ["originador", "receptor", "fecha_hora", "tipo_llamada"]
        for col in required:
            if col not in df.columns:
                df[col] = pd.NA

        # --- 3. NORMALIZACIÓN ---
        print("🧹 Limpiando y normalizando números telefónicos...")
        if "originador" in df.columns:
            df["originador"] = df["originador"].apply(normalizar_numero_colombia)
        if "receptor" in df.columns:
            df["receptor"] = df["receptor"].apply(normalizar_numero_colombia)
        
        # --- 4. FECHA ---
        if "fecha_hora" in df.columns:
            print("📅 Procesando fechas con motor robusto...")
            df["fecha_hora"] = df["fecha_hora"].apply(robust_date_parser)
            
            # Borrar filas sin fecha válida
            df.dropna(subset=["fecha_hora"], inplace=True)
        
        if df.empty:
            print("❌ Error: Todas las fechas fueron inválidas o el archivo está vacío.")
            return df 

        # 5. Duración
        if "duracion" in df.columns:
            df["duracion"] = pd.to_numeric(df["duracion"], errors='coerce').fillna(0).astype(int)
        else:
            df["duracion"] = 0

        # 6. Coordenadas (CRÍTICO: Manejo de punto/coma y valores inválidos)
        def corregir_coordenadas(valor):
            if pd.isna(valor) or str(valor).strip() in ["", "?", "nan", "0", "None"]:
                return np.nan
            try:
                # Tu Excel parece usar punto (7.375060), lo cual es estándar.
                # Pero forzamos string y reemplazo por si acaso viene con coma.
                s_val = str(valor).replace(',', '.')
                val_f = float(s_val)
                
                # Corrección solo si es absurdo (ej: 7375060 en vez de 7.375060)
                # Latitud Colombia aprox: -4 a 13
                # Longitud Colombia aprox: -66 a -79
                if abs(val_f) > 180:
                    if abs(val_f) > 100000: val_f /= 1000000
                    else: val_f /= 10000
                
                return val_f
            except:
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