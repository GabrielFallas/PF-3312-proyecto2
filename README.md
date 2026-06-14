# Benchmarking de Servicios de IA — PF-3312 (Proyecto 2)

Banco de pruebas **reproducible y dockerizado** para evaluar empíricamente
servicios cognitivos **locales y de código abierto** en tres categorías:
**LLM** (lenguaje y razonamiento), **STT** (reconocimiento de voz) y
**TTS** (síntesis de voz). Mide latencia, calidad y eficiencia, y consolida
los resultados en tablas y gráficos para el reporte técnico.

> **Privacidad por diseño:** todos los servicios se ejecutan offline en la
> máquina local. No se envía dato alguno a la nube ni se requieren llaves de
> API de pago.

---

## 1. Servicios evaluados (15 = 5 × 3)

| Categoría | Servicios (todos open-source / locales) |
|-----------|------------------------------------------|
| **LLM** (vía Ollama) | `llama3.1:8b`, `mistral:7b`, `phi3.5`, `gemma2:9b`, `qwen2.5:7b` |
| **STT** | faster-whisper, openai-whisper, whisper.cpp, Vosk, wav2vec2 (HF) |
| **TTS** | Piper, Coqui XTTS v2, Kokoro, eSpeak-NG, Bark |

Dimensiones medidas: **latencia** (TTFT/total, RTF), **precisión/calidad**
(WER, valoración cualitativa), **costo/escalabilidad**, **privacidad**,
**customización** e **integración** (ver `report/reporte_tecnico.md`).

---

## 2. Estructura del repositorio

```
benchmarking-ia/
├── docker-compose.yml        # Ollama + app de benchmarking
├── Dockerfile                # imagen de la app
├── config.py                 # catálogo de servicios y parámetros
├── run_all.py                # orquestador (corre todo + consolida)
├── requirements.txt
├── .env.example              # plantilla (copiar a .env)
├── common/                   # timer (TTFT/latencia), métricas (WER/RTF), persistencia
├── benchmarks/               # llm_benchmark · stt_benchmark · tts_benchmark
├── data/                     # prompts e inputs de prueba controlados
├── analysis/                 # consolidación → tablas Markdown + gráficos
├── results/                  # CSV/JSONL crudos (ignorados por git)
└── report/                   # reporte_tecnico.md, pipeline_diagram.md, figures/
```

---

## 3. Ejecución con Docker (recomendado)

Requisitos: **Docker** y **Docker Compose v2**. (Opcional: GPU NVIDIA con
`nvidia-container-toolkit` — descomenta el bloque `deploy` en
`docker-compose.yml`.)

```bash
# 1) Levanta el servidor de LLMs locales
docker compose up -d ollama

# 2) Descarga los 5 modelos LLM (una sola vez; se persisten en un volumen)
docker compose run --rm ollama-pull

# 3) Construye la imagen de la app y corre el banco COMPLETO
docker compose build benchmark
docker compose run --rm benchmark

# --- Variantes ---
# Solo una categoría:
docker compose run --rm benchmark benchmarks/llm_benchmark.py
docker compose run --rm benchmark benchmarks/stt_benchmark.py
docker compose run --rm benchmark benchmarks/tts_benchmark.py
# Solo consolidar resultados:
docker compose run --rm benchmark analysis/build_report_data.py
```

Los resultados (`results/`), gráficos (`report/figures/`) y audios TTS
(`tts_output/`) quedan en el host gracias a los volúmenes montados.

> **STT/TTS dentro de Docker:** coloca el audio de prueba en
> `data/audio/muestra_es.wav` (16 kHz mono) antes de correr STT, y los
> modelos pesados (Vosk, voz Piper) en `models/` según el `.env`.

---

## 4. Ejecución local con entorno virtual (alternativa sin Docker)

```bash
# 1) Crear y activar el entorno virtual
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 2) Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# 3) Configurar variables de entorno
cp .env.example .env        # Windows: copy .env.example .env
#   edita .env si cambias rutas de modelos (Vosk, Piper, whisper.cpp)

# 4) Instalar Ollama y descargar modelos (https://ollama.com)
ollama pull llama3.1:8b && ollama pull mistral:7b && ollama pull phi3.5 \
  && ollama pull gemma2:9b && ollama pull qwen2.5:7b

# 5) Ejecutar
python run_all.py                       # todo
python -m benchmarks.llm_benchmark      # solo LLM
python -m analysis.build_report_data    # consolidar
```

### Dependencias de sistema (solo modo local)
- **ffmpeg** — audio (Whisper/librosa)
- **espeak-ng** — motor TTS baseline
- **Vosk**: descarga un modelo de español de <https://alphacephei.com/vosk/models> a `models/` y apúntalo en `.env`.
- **Piper**: descarga una voz `.onnx` + `.onnx.json` a `models/piper/` y apúntala en `.env`.
- **whisper.cpp**: compila el binario y define `WHISPER_CPP_BIN`/`WHISPER_CPP_MODEL` en `.env`.

---

## 5. Preparar los datos de prueba

| Archivo | Propósito |
|---------|-----------|
| `data/prompts_llm.json` | 5 prompts controlados (razonamiento, instrucciones, JSON, dominio, multilingüe) + System Prompt |
| `data/reference_transcript.txt` | transcripción humana de referencia (para el WER) |
| `data/audio/muestra_es.wav` | audio en español que **debe corresponder** a la transcripción de referencia |
| `data/tts_text_es.txt` | texto a sintetizar en el benchmark de TTS |

Generar el WAV de prueba a 16 kHz mono:
```bash
ffmpeg -i tu_audio.mp3 -ar 16000 -ac 1 data/audio/muestra_es.wav
```

---

## 6. Metodología de medición (resumen)

- Cada prueba se ejecuta **`N_RUNS` veces (≥ 5)** más **1 corrida de
  calentamiento** que se **descarta** del promedio.
- **LLM:** se mide **TTFT** y latencia total vía *streaming*; se registra
  tokens/seg reportado por Ollama. Temperatura fijada en 0 para reproducibilidad.
- **STT:** latencia total, **RTF** y **WER** contra la referencia.
- **TTS:** latencia de síntesis, duración del audio y **RTF**; el WAV se guarda
  para la valoración cualitativa de naturalidad.
- Toda ejecución individual se persiste en `results/*.csv` (formato largo).

---

## 7. Generar el reporte en PDF (Pandoc)

El reporte se escribe en Markdown (`report/reporte_tecnico.md`) e incorpora las
tablas/figuras generadas por `analysis/build_report_data.py`.

```bash
# Requiere Pandoc y un motor LaTeX (TeX Live / MiKTeX) para PDF.
cd report
pandoc reporte_tecnico.md -o reporte_tecnico.pdf \
  --pdf-engine=xelatex \
  --toc --number-sections \
  -V geometry:margin=2.5cm -V lang=es -V mainfont="Calibri"
```

Los diagramas Mermaid (`pipeline_diagram.md`) se renderizan en GitHub o se
exportan a PNG con `mermaid-cli` (`mmdc`) para incrustarlos en el PDF.

---

## 8. Seguridad y buenas prácticas

- **Nunca** se suben llaves ni el archivo `.env` (ver `.gitignore`).
- Este proyecto no usa APIs de pago: no hay credenciales que exponer.
- El código de integración es **original**; no incluye plantillas de terceros.

---

## Licencia y autoría

Trabajo individual para el curso **PF-3312 — Laboratorio de Agentes Virtuales
Inteligentes**, Universidad de Costa Rica, I Ciclo 2026. Autoría propia.
