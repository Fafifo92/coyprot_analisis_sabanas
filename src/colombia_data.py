import pandas as pd
import math
import os
import sys
import unicodedata

# --- CONFIGURACIÓN DE RUTA ---
def get_db_path():
    """Encuentra el CSV sin importar si corres desde src/ o desde la raíz"""
    # Intento 1: Ruta relativa desde src/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "static", "db", "municipios_colombia.csv")
    
    if os.path.exists(path):
        return path
        
    # Intento 2: Si estamos congelados con PyInstaller
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "static", "db", "municipios_colombia.csv")
        
    return path

# --- CARGA DE DATOS ---
_df_municipios = None

def cargar_municipios():
    global _df_municipios
    path = get_db_path()
    
    if os.path.exists(path):
        try:
            # LEER CON UTF-8-SIG (Para manejar las tildes que generó tu script)
            _df_municipios = pd.read_csv(path, sep=';', encoding='utf-8-sig')
            
            # Normalizar para búsquedas (crear columna sin tildes oculta)
            _df_municipios['Muni_Norm'] = _df_municipios['Municipio'].apply(lambda x: normalizar_texto(str(x)))
            _df_municipios['Depto_Norm'] = _df_municipios['Departamento'].apply(lambda x: normalizar_texto(str(x)))
            
            print(f"🇨🇴 Base de datos geográfica cargada: {len(_df_municipios)} municipios.")
        except Exception as e:
            print(f"❌ Error leyendo municipios_colombia.csv: {e}")
            _df_municipios = pd.DataFrame()
    else:
        print(f"⚠️ No se encontró la base de datos en: {path}")
        _df_municipios = pd.DataFrame()

def normalizar_texto(texto):
    """Quita tildes para comparar (BOGOTÁ -> BOGOTA)"""
    if not isinstance(texto, str): return ""
    s = unicodedata.normalize('NFD', texto)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.upper().strip()

# Cargar al importar
cargar_municipios()

# --- FUNCIONES MATEMÁTICAS ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    """Fórmula de Haversine (Distancia en Km)"""
    try:
        R = 6371 # Radio tierra km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    except:
        return float('inf')

def obtener_ubicacion_completa(lat, lon):
    """
    Recibe Lat/Lon y devuelve (Departamento, Municipio) del punto más cercano.
    """
    global _df_municipios
    if _df_municipios is None or _df_municipios.empty:
        return "Desconocido", "Desconocido"
        
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return "Desconocido", "Desconocido"

    # Optimización: Buscar solo en un radio de ~100km (1 grado latitud)
    lat_min, lat_max = lat - 1, lat + 1
    lon_min, lon_max = lon - 1, lon + 1
    
    df_cerca = _df_municipios[
        (_df_municipios['Latitud'] > lat_min) & (_df_municipios['Latitud'] < lat_max) &
        (_df_municipios['Longitud'] > lon_min) & (_df_municipios['Longitud'] < lon_max)
    ]
    
    # Si no hay nada cerca, buscar en todo el país (caso raro)
    df_search = df_cerca if not df_cerca.empty else _df_municipios
    
    min_dist = float('inf')
    best_muni = "Desconocido"
    best_depto = "Desconocido"

    for row in df_search.itertuples(index=False):
        dist = calcular_distancia(lat, lon, getattr(row, 'Latitud', 0), getattr(row, 'Longitud', 0))
        if dist < min_dist:
            min_dist = dist
            best_muni = getattr(row, 'Municipio', 'Desconocido')
            best_depto = getattr(row, 'Departamento', 'Desconocido')
            
    # Umbral de precisión: si está a menos de 30km, asignamos el municipio.
    # Si no, es zona rural lejana.
    if min_dist < 30:
        return best_depto, best_muni
    else:
        # Devolvemos el más cercano igual, pero indicando lejanía si quisieras
        return best_depto, best_muni 

def inferir_municipio_y_coords(nombre_celda):
    """
    Intenta adivinar coordenadas buscando el nombre del municipio dentro del texto de la celda.
    Ej: "ANT.MEDELLIN-2" -> Encuentra "MEDELLIN" -> Devuelve coords de Medellín.
    """
    global _df_municipios
    if _df_municipios is None or _df_municipios.empty: return None, None, None
    if not nombre_celda or not isinstance(nombre_celda, str): return None, None, None
    
    texto_sucio = nombre_celda.upper().strip()
    texto_norm = normalizar_texto(texto_sucio) # "ANT.MEDELLIN"
    
    # Buscar coincidencia exacta de palabra
    for row in _df_municipios.itertuples(index=False):
        muni_norm = getattr(row, 'Muni_Norm', '') # "MEDELLIN"
        
        # Evitar falsos positivos con nombres cortos (ej: "Ica", "Une")
        if len(muni_norm) < 4: continue
            
        if muni_norm in texto_norm:
            return getattr(row, 'Municipio', None), getattr(row, 'Latitud', None), getattr(row, 'Longitud', None)
            
    return None, None, None
