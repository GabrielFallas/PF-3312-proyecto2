# ============================================================
#  Dockerfile - Banco de pruebas de servicios de IA (PF-3312)
#  Imagen de la APLICACION de benchmarking (scripts Python).
#  Ollama corre en su propio contenedor (ver docker-compose.yml).
# ============================================================
FROM python:3.11-slim

# Evita prompts interactivos y bytecode .pyc; logs sin buffer.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- Dependencias de sistema ---
#   ffmpeg      : decodificacion/resampleo de audio (Whisper, librosa)
#   espeak-ng   : motor TTS baseline usado por el benchmark
#   libsndfile1 : lectura/escritura WAV (soundfile)
#   build-essential: compilacion de wheels que lo requieran
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        espeak-ng \
        libsndfile1 \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependencias primero para aprovechar la cache de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia el codigo del proyecto.
COPY . .

# El host de Ollama dentro de la red de compose es el servicio "ollama".
ENV OLLAMA_HOST=http://ollama:11434 \
    RESULTS_DIR=results

# Por defecto ejecuta el banco completo; se puede sobrescribir el comando.
ENTRYPOINT ["python"]
CMD ["run_all.py"]
