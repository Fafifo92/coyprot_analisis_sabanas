import os
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import logging

logger = logging.getLogger()
plt.style.use('default')

def generar_grafico_top_llamadas(datos, columna, titulo, output_path, nombres_asignados=None, ascendente=False):
    """
    Genera gráfico de barras Top 10 blindado contra errores de ordenamiento.
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