import os
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

def generar_grafico_top_llamadas(datos, columna, titulo, output_path, ascendente=False):
    """
    Genera un gráfico de barras con el top de llamadas realizadas o recibidas.
    """
    if datos.empty:
        print(f"⚠️ No hay datos suficientes para generar {titulo}.")
        return None
    
    top_datos = datos[columna].value_counts().sort_values(ascending=ascendente).head(10)  # Tomar los 10 más frecuentes o menos frecuentes
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x=top_datos.index, y=top_datos.values, hue=top_datos.index, legend=False)
    plt.xlabel("Número")
    plt.ylabel("Frecuencia")
    plt.title(titulo)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"✅ {titulo} guardado en: {output_path}")
    return output_path

def generar_grafico_horario_llamadas(datos, output_path):
    """
    Genera un gráfico de líneas con la frecuencia de llamadas por hora.
    """
    if "fecha_hora" not in datos.columns:
        print("⚠️ No hay datos de fecha y hora para generar el gráfico.")
        return None
    
    datos["hora"] = datos["fecha_hora"].dt.hour
    conteo_horas = datos["hora"].value_counts().sort_index()
    
    plt.figure(figsize=(10, 5))
    sns.lineplot(x=conteo_horas.index, y=conteo_horas.values, marker="o", color="blue")
    plt.xlabel("Hora del día")
    plt.ylabel("Número de llamadas")
    plt.title("Frecuencia de llamadas por hora")
    plt.xticks(range(24))
    plt.grid(True)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"✅ Gráfico de llamadas por hora guardado en: {output_path}")
    return output_path

def generar_graficos_todos(datos):
    """
    Genera todos los gráficos de llamadas, separando entrantes y salientes.
    """
    output_dir = "output/graphics"
    os.makedirs(output_dir, exist_ok=True)
    
    # Top llamadas
    generar_grafico_top_llamadas(datos, "originador", "Top Llamadas Recibidas", os.path.join(output_dir, "top_llamadas_recibidas.png"))
    generar_grafico_top_llamadas(datos, "receptor", "Top Llamadas Realizadas", os.path.join(output_dir, "top_llamadas_realizadas.png"))
       
    # Gráfico horario
    generar_grafico_horario_llamadas(datos, os.path.join(output_dir, "grafico_horario_llamadas.png"))
    
    print("✅ Todos los gráficos han sido generados correctamente.")
    
if __name__ == "__main__":
    archivo_excel = "ruta_al_archivo.xlsx"  # Cambiar por la ruta real
    df = pd.read_excel(archivo_excel)
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors='coerce')
    df.dropna(subset=["fecha_hora"], inplace=True)
    
    generar_graficos_todos(df)