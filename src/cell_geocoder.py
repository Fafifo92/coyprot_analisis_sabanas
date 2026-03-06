
import pandas as pd
import os
import re

class CellGeocoder:
    def __init__(self, db_path):
        self.db_path = db_path
        self.df_sitios = None
        self.cargar_base_datos()

    def limpiar_nombre_sitio(self, nombre):
        """
        Elimina sufijos técnicos (_LTE, _UMTS, _1, _A, _R1, etc.)
        para encontrar el nombre RAÍZ del sitio físico.
        Ej: 'ANT.BARBOSA-2_R1' -> 'ANT.BARBOSA-2'
        """
        if pd.isna(nombre):
            return ""
        
        nombre = str(nombre).upper().strip()
        
        # Regex: Busca guion bajo seguido de 1-4 carácteres o tecnologías al final
        patron = r'_([A-Z0-9]{1,4}|LTE|UMTS|GSM)$'
        
        # Ejecutamos dos veces para casos anidados
        nombre_limpio = re.sub(patron, '', nombre)
        nombre_limpio = re.sub(patron, '', nombre_limpio) 
        
        return nombre_limpio

    def cargar_base_datos(self):
        """
        Carga la base de datos de celdas y agrupa por nombre raíz.
        """
        if not os.path.exists(self.db_path):
            print(f"⚠️ Geocoder: No se encontró la base de datos en {self.db_path}")
            return

        try:
            print(f"🔄 Cargando base de datos de celdas desde {os.path.basename(self.db_path)}...")
            
            df_temp = None
            
            # INTENTO 1: Leer con Punto y Coma (;) y saltar líneas malas (on_bad_lines='skip')
            # Usamos engine='python' que es más robusto para detectar errores
            try:
                df_temp = pd.read_csv(
                    self.db_path, 
                    sep=';', 
                    encoding='latin-1', 
                    on_bad_lines='skip', 
                    engine='python'
                )
            except Exception as e1:
                # Si falla, INTENTO 2: Leer con Coma (,)
                try:
                    df_temp = pd.read_csv(
                        self.db_path, 
                        sep=',', 
                        encoding='latin-1', 
                        on_bad_lines='skip', 
                        engine='python'
                    )
                except Exception as e2:
                    print(f"❌ Error crítico leyendo archivo: {e2}")
                    return

            if df_temp is None or df_temp.empty:
                print("❌ El archivo de celdas parece estar vacío o ilegible.")
                return

            # Normalizar nombres de columnas (quitar espacios extra)
            df_temp.columns = [c.strip() for c in df_temp.columns]
            
            # Identificar columnas clave dinámicamente
            col_nombre = next((c for c in df_temp.columns if "BTS" in c or "Nombre" in c or "Cell" in c), None)
            col_lat = next((c for c in df_temp.columns if "Latitud" in c or "LAT" in c.upper()), None)
            col_lon = next((c for c in df_temp.columns if "Longitud" in c or "LON" in c.upper()), None)

            if not col_nombre or not col_lat or not col_lon:
                print(f"❌ Geocoder Error: No se encontraron columnas BTS/Lat/Lon. Columnas disponibles: {df_temp.columns.tolist()}")
                return

            # Estandarizar
            df_temp = df_temp.rename(columns={col_nombre: 'raw_name', col_lat: 'lat', col_lon: 'lon'})
            
            # Limpieza de coordenadas
            # Reemplazar comas por puntos en las coordenadas (ej: 4,71 -> 4.71)
            if df_temp['lat'].dtype == object:
                df_temp['lat'] = df_temp['lat'].astype(str).str.replace(',', '.', regex=False)
            if df_temp['lon'].dtype == object:
                df_temp['lon'] = df_temp['lon'].astype(str).str.replace(',', '.', regex=False)

            df_temp['lat'] = pd.to_numeric(df_temp['lat'], errors='coerce')
            df_temp['lon'] = pd.to_numeric(df_temp['lon'], errors='coerce')
            
            df_temp.dropna(subset=['lat', 'lon'], inplace=True)

            # Crear la columna RAÍZ (el nombre limpio)
            df_temp['site_root'] = df_temp['raw_name'].apply(self.limpiar_nombre_sitio)
            
            # Agrupar: Si hay 3 celdas (S1, S2, S3) en el mismo sitio, promediamos sus coordenadas
            self.df_sitios = df_temp.groupby('site_root')[['lat', 'lon']].mean().reset_index()
            
            print(f"✅ Base de celdas indexada: {len(self.df_sitios)} sitios únicos.")

        except Exception as e:
            print(f"❌ Error general en Geocoder: {e}")
            self.df_sitios = None

    def buscar_coordenadas(self, df_cdr, col_nombre_celda):
        """
        Cruza la sábana de llamadas con la base de datos de celdas.
        """
        if self.df_sitios is None or df_cdr is None or df_cdr.empty:
            return df_cdr

        # 1. Crear llave temporal limpia en el CDR
        df_cdr['temp_root'] = df_cdr[col_nombre_celda].apply(self.limpiar_nombre_sitio)
        
        # 2. Guardar índice original para no desordenar los datos
        df_cdr['orig_index'] = df_cdr.index

        # 3. MERGE (LEFT JOIN)
        df_merged = pd.merge(
            df_cdr,
            self.df_sitios,
            left_on='temp_root',
            right_on='site_root',
            how='left'
        )

        # 4. Rellenar coordenadas faltantes
        if 'latitud_n' not in df_merged.columns:
            df_merged['latitud_n'] = df_merged['lat']
        else:
            df_merged['latitud_n'] = df_merged['latitud_n'].fillna(df_merged['lat'])

        if 'longitud_w' not in df_merged.columns:
            df_merged['longitud_w'] = df_merged['lon']
        else:
            df_merged['longitud_w'] = df_merged['longitud_w'].fillna(df_merged['lon'])

        # Estadísticas
        total = len(df_merged)
        con_coords = df_merged['latitud_n'].notna().sum()
        print(f"📍 Geocodificación por celdas: {con_coords} registros ubicados.")

        # 5. Limpieza final
        cols_drop = ['temp_root', 'site_root', 'lat', 'lon', 'orig_index']
        df_merged.drop(columns=[c for c in cols_drop if c in df_merged.columns], inplace=True)
        
        return df_merged
