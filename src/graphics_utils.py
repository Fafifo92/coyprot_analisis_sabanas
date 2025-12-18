import os
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import logging

# Configuración básica
logger = logging.getLogger()
plt.style.use('default')

def generar_grafico_top_llamadas(datos, columna, titulo, output_path, nombres_asignados=None, ascendente=False):
    """
    Genera gráfico de barras Top 10 de frecuencia de llamadas.
    """
    if datos is None or datos.empty or columna not in datos.columns:
        return None

    try:
        # Calcular Top 10
        # BLINDAJE: value_counts ordena solo (descendente por defecto)
        conteo = datos[columna].astype(str).value_counts()
        
        # Aplicar orden explícito seguro
        if ascendente:
            conteo = conteo.sort_values(ascending=True)
        else:
            conteo = conteo.sort_values(ascending=False)
            
        top_datos = conteo.head(10)
    except Exception as e:
        logger.error(f"Error calculando frecuencias para '{titulo}': {e}")
        return None

    if top_datos.empty:
        return None

    # Etiquetas personalizadas
    etiquetas = []
    for num_str in top_datos.index:
        nombre = nombres_asignados.get(num_str) if nombres_asignados else None
        etiquetas.append(f"{num_str}\n({nombre})" if nombre else num_str)

    # Generar Gráfico
    fig, ax = plt.subplots(figsize=(12, 7))
    try:
        sns.barplot(x=etiquetas, y=top_datos.values, palette="tab10", ax=ax)
    except:
        plt.close(fig); return None

    ax.set_title(titulo, fontsize=14, fontweight='bold')
    ax.tick_params(axis='x', labelsize=9)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
    except:
        plt.close(fig)

def generar_grafico_horario_llamadas(datos, output_path):
    """
    Genera un gráfico de línea con la actividad por hora del día (0-23h).
    """
    if datos is None or datos.empty or "fecha_hora" not in datos.columns:
        return None
    
    # Copia segura y validación de tipos
    try:
        df = datos.copy()
        if not pd.api.types.is_datetime64_any_dtype(df['fecha_hora']):
            df['fecha_hora'] = pd.to_datetime(df['fecha_hora'], errors='coerce')
        df.dropna(subset=['fecha_hora'], inplace=True)
        
        if df.empty: return None

        # Conteo por hora
        df["hora"] = df["fecha_hora"].dt.hour
        conteo = df["hora"].value_counts().sort_index().reindex(range(24), fill_value=0)
    except:
        return None

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.lineplot(x=conteo.index, y=conteo.values, marker="o", color="dodgerblue", ax=ax)
    
    ax.set_title("Frecuencia por Hora", fontsize=14)
    ax.set_xticks(range(24))
    ax.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path, dpi=100)
        plt.close(fig)
    except:
        plt.close(fig)

def generar_grafico_top_ubicacion(datos, col_numero, col_ubicacion, titulo, output_path, nombres_asignados=None):
    """
    Genera gráfico de barras: Top 10 Números y muestra debajo su ubicación más frecuente.
    Útil para mostrar 'Desde dónde llaman' o 'Dónde estaba al contestar'.
    """
    if datos is None or datos.empty or col_numero not in datos.columns:
        return None

    try:
        # 1. Contar frecuencias de números (Top 10)
        conteo = datos[col_numero].astype(str).value_counts().head(10)
        
        if conteo.empty: return None

        etiquetas = []
        valores = []

        # 2. Para cada número del top, buscar su ubicación más frecuente (Moda)
        for numero in conteo.index:
            valores.append(conteo[numero])
            
            # Filtrar filas de este número
            sub_df = datos[datos[col_numero].astype(str) == numero]
            
            # Calcular ubicación más común
            ubicacion_str = "Desconocida"
            
            if col_ubicacion in sub_df.columns:
                # Obtenemos la moda (valor más repetido)
                modas = sub_df[col_ubicacion].dropna().mode()
                
                if not modas.empty:
                    raw_loc = str(modas[0]).upper()
                    
                    # --- Limpieza Visual para el Gráfico ---
                    # Objetivo: Convertir "ANT.BARBOSA-2_R1" en "BARBOSA"
                    
                    # 1. Si tiene punto (ANT.BARBOSA), tomar la segunda parte
                    if '.' in raw_loc:
                        parts = raw_loc.split('.')
                        if len(parts) > 1:
                            raw_loc = parts[1]
                    
                    # 2. Eliminar sufijos técnicos después de guiones o guiones bajos
                    # Ej: BARBOSA-2 -> BARBOSA
                    raw_loc = raw_loc.split('-')[0].split('_')[0]
                    
                    ubicacion_str = raw_loc.strip()

            # Nombre Alias
            alias = nombres_asignados.get(numero, "") if nombres_asignados else ""
            
            # Construir etiqueta de 3 líneas:
            # NUMERO
            # (ALIAS)
            # [UBICACION]
            lbl = f"{numero}"
            if alias: lbl += f"\n({alias})"
            lbl += f"\n📍 {ubicacion_str}"
            
            etiquetas.append(lbl)

        # Generar Gráfico
        # Aumentamos la altura (figsize) para que quepan las etiquetas largas
        fig, ax = plt.subplots(figsize=(12, 8)) 
        
        # Usamos una paleta diferente para diferenciarlo visualmente (viridis)
        sns.barplot(x=etiquetas, y=valores, palette="viridis", ax=ax)

        ax.set_title(titulo, fontsize=14, fontweight='bold')
        ax.set_ylabel("Cantidad de Llamadas")
        
        # Ajustar tamaño de fuente del eje X para que se lea la ubicación
        ax.tick_params(axis='x', labelsize=8.5)
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        
    except Exception as e:
        logger.error(f"Error gráfico top ubicación: {e}")
        try: plt.close(fig)
        except: pass