import pandas as pd
import numpy as np
import time
import os
import sys

# Mocking folium and other imports that might not be needed for pure iteration benchmarking
# but are used in the original code.
# However, the task is specifically about iterrows vs itertuples.

def benchmark_iterrows(df):
    start = time.time()
    count = 0
    for _, row in df.iterrows():
        lat, lon = row["latitud_n"], row["longitud_w"]
        tipo = str(row.get("tipo_llamada", "desconocido")).lower()
        if "dato" in tipo:
            cid = str(row.get("cell_identity_decimal", ""))
            celda = str(row.get("nombre_celda", ""))
            if cid and cid not in ["nan", "None", ""]: num = f"Celda: {cid}"
            elif celda and celda not in ["nan", "None", ""]: num = f"Antena: {celda}"
            else: num = "Tráfico de Datos"
        elif tipo == "saliente":
            num = str(row.get("receptor", "N/A"))
        else:
            num = str(row.get("originador", "N/A"))

        # Simulating some of the logic inside the loop
        fecha_hora = row['fecha_hora']
        count += 1
    end = time.time()
    return end - start

def benchmark_itertuples(df):
    start = time.time()
    count = 0
    # Pre-calculate column indices if we want even more speed, but itertuples is already much faster
    for row in df.itertuples(index=False):
        # itertuples returns a namedtuple, access by attribute
        lat, lon = row.latitud_n, row.longitud_w
        # itertuples doesn't have .get(), we use getattr
        tipo = str(getattr(row, "tipo_llamada", "desconocido")).lower()

        if "dato" in tipo:
            cid = str(getattr(row, "cell_identity_decimal", ""))
            celda = str(getattr(row, "nombre_celda", ""))
            if cid and cid not in ["nan", "None", ""]: num = f"Celda: {cid}"
            elif celda and celda not in ["nan", "None", ""]: num = f"Antena: {celda}"
            else: num = "Tráfico de Datos"
        elif tipo == "saliente":
            num = str(getattr(row, "receptor", "N/A"))
        else:
            num = str(getattr(row, "originador", "N/A"))

        fecha_hora = row.fecha_hora
        count += 1
    end = time.time()
    return end - start

if __name__ == "__main__":
    n = 100000
    df = pd.DataFrame({
        "latitud_n": np.random.uniform(-90, 90, n),
        "longitud_w": np.random.uniform(-180, 180, n),
        "tipo_llamada": np.random.choice(["entrante", "saliente", "dato"], n),
        "cell_identity_decimal": np.random.choice(["123", "456", None], n),
        "nombre_celda": np.random.choice(["Celda1", "Celda2", None], n),
        "receptor": np.random.choice(["123456", "654321"], n),
        "originador": np.random.choice(["111111", "222222"], n),
        "fecha_hora": pd.to_datetime(np.random.randint(0, 10**9, n), unit='s')
    })

    print(f"Benchmarking with {n} rows...")
    t_iterrows = benchmark_iterrows(df)
    print(f"iterrows: {t_iterrows:.4f}s")

    t_itertuples = benchmark_itertuples(df)
    print(f"itertuples: {t_itertuples:.4f}s")

    print(f"Improvement: {(t_iterrows - t_itertuples) / t_iterrows * 100:.2f}%")
