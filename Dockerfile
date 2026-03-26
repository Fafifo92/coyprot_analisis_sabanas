# Usa la imagen oficial de Python 3.11 delgada
FROM python:3.11-slim

# Evita que Python escriba archivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Evita que Python haga buffer de stdout y stderr (útil para logs en Docker)
ENV PYTHONUNBUFFERED=1

# Instala dependencias del sistema necesarias para compilar/gráficos
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia e instala requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia todo el código fuente del backend
COPY src/ /app/src/
COPY static/ /app/static/
COPY templates/ /app/templates/

# Directorios de la app temporal
RUN mkdir -p /app/uploads /app/output /app/logs

# Expone el puerto que usa FastAPI por defecto
EXPOSE 8000

# Comando para iniciar la aplicación (Asumiendo uvicorn con src.api.main)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
