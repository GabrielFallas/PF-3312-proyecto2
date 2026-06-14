# Benchmarking de Servicios de IA — PF-3312 (Proyecto 2)

Banco de pruebas **reproducible y dockerizado** para evaluar empíricamente
servicios cognitivos en tres categorías: **LLM** (lenguaje y razonamiento),
**STT** (reconocimiento de voz) y **TTS** (síntesis de voz). La muestra incluye
el **balance** que exige el enunciado: comercial de alta gama en la nube,
comercial de bajo costo/alta velocidad y open-source local. Mide latencia,
calidad y eficiencia, y consolida los resultados en tablas y gráficos.

> **Costo cero:** los servicios en la nube se usan vía su **capa gratuita** y se
> activan solo si configuras su API key en `.env`; los locales corren 100 %
> offline. Las llaves nunca se versionan (`.gitignore`). Si solo quieres la ruta
> local y privada, usa la bandera `--only-local` en cualquier benchmark.

---

## 1. Servicios evaluados (≥ 15, balance de 3 tipos)

El enunciado exige un **balance representativo**: comercial de alta gama en la
nube, comercial de bajo costo/alta velocidad, y open-source local. Para mantener
el **costo en cero**, los servicios en la nube se consumen vía su **capa
gratuita (free tier)**. Cada servicio en la nube se **activa solo si su API key
está en `.env`**; si no, se omite y el resto continúa.

| Categoría | 🟣 Nube alta gama | 🔵 Nube bajo costo/rápido | 🟢 Local offline |
|-----------|-------------------|---------------------------|------------------|
| **LLM** | Gemini 2.5 Pro | Gemini 2.5 Flash · Groq Llama 3.3 70B | Llama 3.1 8B · Mistral 7B · Phi-3.5 · Gemma 2 9B · Qwen 2.5 7B |
| **STT** | Deepgram nova-2 · AssemblyAI | Groq Whisper large-v3 | faster-whisper · openai-whisper · whisper.cpp · Vosk · wav2vec2 |
| **TTS** | ElevenLabs multilingual v2 | ElevenLabs Flash v2.5 · Deepgram Aura 2 | Piper · Coqui XTTS v2 · Kokoro · eSpeak-NG · Bark |

> Se evitan **OpenAI, Anthropic y Azure** por no ofrecer un acceso gratuito
> práctico. Se usan solo proveedores con **free tier real**.

**Free tiers (registro gratuito):** [Google AI Studio](https://aistudio.google.com/apikey)
(Gemini) · [Groq](https://console.groq.com/keys) · [Deepgram](https://console.deepgram.com)
· [AssemblyAI](https://www.assemblyai.com) · [ElevenLabs](https://elevenlabs.io).
Copia cada llave a tu `.env` (nunca a `.env.example`).

> **Antes de gastar cuota**, valida tus llaves y descubre los modelos vigentes
> con el *preflight* (solo lectura, no consume uso):
> `python -m tools.check_services --show-models`

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

Generar el WAV de prueba a 16 kHz mono (dos opciones):
```bash
# A) Sintetizar la referencia con ElevenLabs (reproducible, sin ffmpeg):
python -m tools.make_test_audio
# B) Convertir un audio real propio:
ffmpeg -i tu_audio.mp3 -ar 16000 -ac 1 data/audio/muestra_es.wav
```

> **Resultados incluidos:** este repositorio ya trae una corrida completa real en
> `results/*.csv`, las figuras en `report/figures/` y las tablas consolidadas en
> `report/tablas_generadas.md`, ejecutadas sobre un equipo i7-13700KF + **RTX
> 5070 Ti** (LLM locales en GPU) descrito en el reporte. Para reproducir desde
> cero, borra `results/` y vuelve a correr los pasos anteriores.

> **GPU automática:** `docker-compose.yml` ya habilita la GPU NVIDIA para Ollama
> (bloque `deploy`). Si tu equipo no tiene GPU, coméntalo y correrá en CPU.

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

### Conservación de cuota (free tier)
Para no agotar las capas gratuitas durante las pruebas, los servicios **en la
nube** aplican automáticamente (configurable en `.env`):
- `CLOUD_MAX_OUTPUT_TOKENS` (def. 256): topa los tokens de salida de los LLM en
  la nube (los locales no se ven afectados).
- `CLOUD_N_RUNS` (def. = `N_RUNS`): permite usar menos corridas en la nube
  durante la exploración; **súbelo a ≥ 5 para el benchmark final** que reportas.
- `CLOUD_REQUEST_DELAY` (def. 1.5 s): pausa entre llamadas para respetar el
  límite de peticiones por minuto.

Ejecuta siempre antes `python -m tools.check_services` para validar llaves y ver
modelos vigentes **sin consumir cuota**.

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
