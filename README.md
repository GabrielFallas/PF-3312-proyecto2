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
| **LLM** | Gemini 2.5 Pro¹ · gpt-oss-120B (Groq) · Llama 4 Scout (Groq) | Gemini 2.5 Flash · Gemini 2.5 Flash-Lite · Groq Llama 3.3 70B | Llama 3.1 8B · Mistral 7B · Phi-3.5 · Gemma 2 9B · Qwen 2.5 7B |
| **STT** | Deepgram nova-2 · AssemblyAI | Groq Whisper large-v3 | faster-whisper · openai-whisper · whisper.cpp · Vosk · wav2vec2 |
| **TTS** | ElevenLabs multilingual v2 | ElevenLabs Flash v2.5 · Deepgram Aura 2 | Piper · Coqui XTTS v2 · Kokoro · eSpeak-NG · Bark |

> ¹ **Gemini 2.5 Pro** se incluye como referencia de gama alta, pero su capa
> gratuita devuelve **HTTP 429** desde la primera petición (no es usable sin
> facturación). El punto empírico de "alta gama en la nube" lo aportan
> **gpt-oss-120B** (120 B, pesos abiertos de OpenAI) y **Llama 4 Scout**, modelos
> *flagship* servidos sobre la LPU de Groq con *free tier* real. Ver el reporte.

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
├── docker-compose.yml        # Ollama + app de benchmarking (CPU, corre en cualquier equipo)
├── docker-compose.gpu.yml    # override OPCIONAL para GPU NVIDIA
├── Dockerfile                # imagen de la app
├── config.py                 # catálogo de servicios y parámetros
├── run_all.py                # orquestador (corre todo + consolida)
├── requirements.txt
├── .env.example              # plantilla (copiar a .env)
├── common/                   # timer (TTFT/latencia), métricas (WER/RTF), persistencia
├── benchmarks/               # llm_benchmark · stt_benchmark · tts_benchmark
├── tools/                    # check_services (preflight) · setup_models · make_test_audio
├── data/                     # prompts, audio de prueba e inputs controlados (versionados)
├── analysis/                 # consolidación → tablas Markdown + gráficos
├── results/                  # CSV/JSONL crudos (corrida real incluida)
└── report/                   # reporte_tecnico.md/.pdf, pipeline_diagram.md, figures/, build_pdf.sh
```

---

## 3. Ejecución con Docker (recomendado)

Requisito único: **Docker** y **Docker Compose v2**. El compose **base no exige
GPU**, así que corre en cualquier máquina limpia (solo CPU). La aceleración por
GPU es un **override opcional** (ver más abajo).

```bash
# 0) Clona el repo y entra a la carpeta
git clone https://github.com/GabrielFallas/PF-3312-proyecto2.git
cd PF-3312-proyecto2/benchmarking-ia

# 1) (Opcional) Configura las API keys de la nube. Sin esto, los servicios en la
#    nube se OMITEN y el banco corre solo con los modelos locales.
cp .env.example .env        # Windows: copy .env.example .env
#   edita .env y pega tus llaves de free tier (Gemini, Groq, Deepgram, ...)

# 2) Levanta el servidor de LLMs locales (CPU)
docker compose up -d ollama

# 3) Descarga los 5 modelos LLM locales (una sola vez; se persisten en un volumen)
docker compose run --rm ollama-pull

# 4) Descarga los modelos locales de STT/TTS (Vosk + voces Piper) al host
docker compose run --rm benchmark -m tools.setup_models

# 5) Construye la imagen de la app y corre el banco COMPLETO
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

### Aceleración por GPU NVIDIA (opcional)

Si el host tiene una GPU NVIDIA y `nvidia-container-toolkit`, añade el override
de GPU **en cada comando** para que Ollama use la tarjeta:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d ollama
docker compose -f docker-compose.yml -f docker-compose.gpu.yml run --rm benchmark
```

> **Datos de prueba ya incluidos:** el audio STT (`data/audio/muestra_es.wav`,
> 16 kHz mono) viene versionado en el repo, así que el benchmark de STT corre sin
> ninguna clave de API. Los modelos locales (Vosk/Piper) los baja el paso 4.

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

# 4) Descargar modelos locales de STT/TTS (Vosk + voces Piper) -> models/
python -m tools.setup_models

# 5) Instalar Ollama y descargar los LLM locales (https://ollama.com)
ollama pull llama3.1:8b && ollama pull mistral:7b && ollama pull phi3.5 \
  && ollama pull gemma2:9b && ollama pull qwen2.5:7b

# 6) Ejecutar
python run_all.py                       # todo
python -m benchmarks.llm_benchmark      # solo LLM
python -m benchmarks.stt_benchmark --only-local   # STT local (sin claves)
python -m analysis.build_report_data    # consolidar
```

### Dependencias de sistema (solo modo local)
- **ffmpeg** — audio (Whisper/librosa)
- **espeak-ng** — motor TTS baseline
- **Vosk** y **Piper**: los descarga automáticamente `python -m tools.setup_models`
  a `models/` (rutas ya configuradas en `.env.example`). No requiere pasos manuales.
- **whisper.cpp** (opcional): compila el binario y define `WHISPER_CPP_BIN`/`WHISPER_CPP_MODEL` en `.env`.

---

## 5. Preparar los datos de prueba

| Archivo | Propósito |
|---------|-----------|
| `data/prompts_llm.json` | 5 prompts controlados (razonamiento, instrucciones, JSON, dominio, multilingüe) + System Prompt |
| `data/reference_transcript.txt` | transcripción humana de referencia (para el WER) |
| `data/audio/muestra_es.wav` | audio en español que **debe corresponder** a la transcripción de referencia |
| `data/tts_text_es.txt` | texto a sintetizar en el benchmark de TTS |

El audio de prueba **ya viene incluido** en el repo (`data/audio/muestra_es.wav`,
16 kHz mono), por lo que no hay que generarlo. Si deseas regenerarlo o usar otro:
```bash
# A) Regenerar la referencia con ElevenLabs (requiere ELEVENLABS_API_KEY):
python -m tools.make_test_audio
# B) Convertir un audio real propio (requiere ffmpeg):
ffmpeg -i tu_audio.mp3 -ar 16000 -ac 1 data/audio/muestra_es.wav
```

> **Resultados incluidos:** este repositorio ya trae una corrida completa real en
> `results/*.csv`, las figuras en `report/figures/` y las tablas consolidadas en
> `report/tablas_generadas.md`, ejecutadas sobre un equipo i7-13700KF + **RTX
> 5070 Ti** (LLM locales en GPU) descrito en el reporte. Para reproducir desde
> cero, borra `results/` y vuelve a correr los pasos anteriores.

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

El PDF final (`report/reporte_tecnico.pdf`) **ya viene generado** en el repo. Para
regenerarlo usa el script reproducible, que sustituye los emojis/símbolos de las
tablas por su etiqueta de texto antes de invocar Pandoc:

```bash
cd report
./build_pdf.sh                 # usa tectonic por defecto
PDF_ENGINE=xelatex ./build_pdf.sh   # si tienes TeX Live / MiKTeX instalado
```

> **Sin LaTeX en el sistema:** descarga el binario portable de
> [tectonic](https://github.com/tectonic-typesetting/tectonic/releases)
> (un único ejecutable, no requiere instalación) y colócalo en el `PATH` o en
> `.tools/`. El script lo detecta automáticamente. Tectonic descarga los paquetes
> LaTeX necesarios la primera vez.

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
