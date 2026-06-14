---
title: "Benchmarking de Servicios de IA para Agentes Virtuales Inteligentes"
subtitle: "Proyecto 2 — Laboratorio PF-3312"
author: "Gabriel Fallas"
date: "I Ciclo 2026 — Universidad de Costa Rica"
lang: es
---

\newpage

# Introducción y Objetivos

El desarrollo de un agente virtual interactivo capaz de conversar por voz exige
seleccionar una arquitectura de servicios cognitivos que equilibre desempeño,
costo, privacidad y facilidad de integración. La elección no puede sustentarse
en la popularidad comercial de una API ni en el tamaño nominal de un modelo:
requiere **evidencia empírica** recolectada bajo condiciones controladas.

Este reporte documenta el diseño, la ejecución y el análisis de un banco de
pruebas (*benchmarking*) sobre **al menos quince servicios** distribuidos en
tres categorías que componen el *pipeline* de comunicación del agente: modelos
de lenguaje (LLM), reconocimiento de voz (STT) y síntesis de voz (TTS). La
muestra mantiene un **balance representativo** de los tres tipos que exige el
enunciado: servicios **comerciales de alta gama en la nube** (p.ej. Gemini,
Deepgram, ElevenLabs), **APIs comerciales de bajo costo o alta velocidad**
(p.ej. Groq, OpenAI tts-1) y **modelos de código abierto de ejecución local
(offline)** (Ollama, Whisper local, Piper, etc.).

Para no incurrir en costos, los servicios en la nube se consumen a través de sus
**capas gratuitas (free tier)**. Esta combinación permite contrastar de forma
empírica los compromisos entre **desempeño en la nube** y **soberanía de datos
local**, dos extremos relevantes para un agente institucional. Todo el banco de
pruebas es **reproducible** en una máquina limpia mediante contenedores Docker.

## Objetivos específicos

1. Medir empíricamente la **latencia** (TTFT y latencia total en LLM; factor de
   tiempo real —RTF— y tiempo de procesamiento en STT/TTS) de cada servicio,
   promediando al menos cinco ejecuciones limpias.
2. Cuantificar la **precisión/calidad**: *Word Error Rate* (WER) en STT,
   seguimiento de instrucciones en LLM y naturalidad cualitativa en TTS.
3. Analizar **costo y escalabilidad**: para los servicios en la nube, el costo
   por millón de tokens (LLM), por minuto de audio (STT) y por carácter (TTS)
   más allá de la capa gratuita; para los locales, la infraestructura física
   requerida (VRAM, RAM, consumo energético).
4. Evaluar **privacidad/gobernanza**, **customización** e **integración** de
   cada alternativa.
5. Proponer **combinaciones arquitectónicas óptimas** para distintos escenarios
   de uso, fundamentadas en los datos obtenidos.

\newpage

# Metodología de Pruebas

## Entorno de ejecución

> **Nota de reproducibilidad:** complete esta tabla con las especificaciones
> reales de la máquina donde ejecutó los benchmarks. Los valores empíricos del
> reporte dependen directamente de este hardware.

| Componente | Especificación |
|------------|----------------|
| CPU | _[p.ej. AMD Ryzen 7 5800H, 8 núcleos / 16 hilos]_ |
| GPU | _[p.ej. NVIDIA RTX 3060 6 GB VRAM / o "sin GPU dedicada"]_ |
| RAM | _[p.ej. 16 GB DDR4]_ |
| Almacenamiento | _[p.ej. SSD NVMe 512 GB]_ |
| Sistema operativo | _[p.ej. Windows 11 + WSL2 / Ubuntu 22.04]_ |
| Runtime de contenedores | Docker Engine __ + Compose v2 |
| Servidor LLM | Ollama __ (contenedor `ollama/ollama:latest`) |
| Python | 3.11 (imagen `python:3.11-slim`) |

Todo el banco de pruebas se ejecuta de forma **contenerizada**: un contenedor
sirve los LLM (Ollama) y otro ejecuta los scripts de medición, comunicándose
por la red interna de Docker Compose. Esto elimina diferencias de entorno y
permite reconstruir el experimento con tres comandos (ver `README.md`).

## Servicios evaluados

La muestra cumple el **balance representativo** exigido por el enunciado,
combinando los tres tipos en cada categoría. Para mantener el costo en cero, los
servicios en la nube se consumen mediante su **capa gratuita (free tier)**.

| Categoría | Nube — alta gama | Nube — bajo costo/rápido | Local — offline |
|-----------|------------------|--------------------------|-----------------|
| **LLM** | Gemini 2.5 Pro | Gemini 2.5 Flash; Groq Llama 3.3 70B | Llama 3.1 8B, Mistral 7B, Phi-3.5, Gemma 2 9B, Qwen 2.5 7B |
| **STT** | Deepgram nova-2; AssemblyAI | Groq Whisper large-v3 | faster-whisper, openai-whisper, whisper.cpp, Vosk, wav2vec2 |
| **TTS** | ElevenLabs multilingual v2 | ElevenLabs Flash v2.5; Deepgram Aura 2 | Piper, Coqui XTTS v2, Kokoro, eSpeak-NG, Bark |

Solo se emplean proveedores con **capa gratuita real**; se descartan OpenAI,
Anthropic y Azure por carecer de acceso gratuito práctico. Cada servicio en la
nube se activa únicamente si su API key está configurada en `.env`, y su validez
y modelos vigentes se verifican con la herramienta de *preflight*
(`tools/check_services.py`) sin consumir cuota de uso.

Así, cada categoría supera el mínimo de 5 servicios e incluye: capacidad de alta
gama en la nube (Gemini 2.5 Pro, Deepgram, ElevenLabs), opciones de bajo
costo/alta velocidad (Gemini 2.5 Flash, Groq, Deepgram Aura) y despliegue 100 %
offline (Ollama, Whisper local, Piper, etc.). Los datos sensibles solo salen de
la máquina en los servicios en la nube; las alternativas locales garantizan
aislamiento absoluto (ver dimensión de privacidad).

## Insumos de prueba controlados

- **LLM** — `data/prompts_llm.json`: cinco prompts que ejercitan razonamiento
  aritmético, seguimiento estricto de instrucciones, salida estructurada (JSON),
  conocimiento de dominio y robustez multilingüe, todos bajo un mismo
  *System Prompt* que fija la persona del agente ("Aurora").
- **STT** — un audio en español de 16 kHz mono (`data/audio/muestra_es.wav`)
  con su transcripción humana de referencia (`data/reference_transcript.txt`)
  para el cálculo de WER.
- **TTS** — un párrafo representativo del dominio (`data/tts_text_es.txt`).

## Herramientas y protocolo de medición

- **Cronometraje:** `time.perf_counter()` (monótono, alta resolución). En LLM se
  consume la API de Ollama en modo *streaming*: el primer fragmento con
  contenido marca el **TTFT** y el evento `done` cierra la latencia total; se
  registra además `tokens/seg` reportado por el motor.
- **Calidad:** WER con la librería `jiwer` (con respaldo propio de Levenshtein
  por palabras) sobre texto normalizado; **RTF = tiempo de procesamiento /
  duración del audio** para STT y TTS.
- **Repeticiones:** `N_RUNS = 5` ejecuciones por prueba **más una corrida de
  calentamiento que se descarta** (mitiga el sesgo de carga inicial de modelo y
  cachés). Temperatura del LLM fijada en `0.0` para reproducibilidad.
- **Persistencia:** cada ejecución individual se anexa a `results/*.csv`
  (formato largo). El script `analysis/build_report_data.py` consolida los
  promedios y genera las tablas y los gráficos de este reporte.

\newpage

# Análisis Comparativo por Categoría

> **Cómo se llenan las tablas empíricas:** ejecute el banco de pruebas
> (`docker compose run --rm benchmark`) y luego
> `python -m analysis.build_report_data`. Los promedios (media ± desviación) y
> los gráficos quedan en `report/tablas_generadas.md` y `report/figures/`.
> Sustituya los marcadores `‹…›` por esos valores e incruste las figuras.

## 3.1 Modelos de Lenguaje (LLM)

### Matriz comparativa (servicios × 6 dimensiones)

| Servicio (tipo) | 1. Latencia (TTFT/total) | 2. Calidad | 3. Costo/escala | 4. Privacidad | 5. Customización | 6. Integración |
|-----------------|--------------------------|-----------|-----------------|---------------|------------------|----------------|
| **Gemini 2.5 Pro** 🟣 nube | ‹med›/‹med› | Muy alta (razonamiento, contexto largo) | Free tier; luego $/1M tokens | Datos salen a Google; opt-out según plan | System instruction, tools, JSON mode | REST/SSE, SDK oficial |
| **Gemini 2.5 Flash** 🔵 nube | ‹med› | Alta (moderno, muy rápido) | Free tier amplio | Datos salen a Google | System instruction, tools, JSON mode | REST/SSE |
| **Groq Llama 3.3 70B** 🔵 nube | ‹med› (TTFT muy bajo) | Alta | Free tier; muy alta velocidad (LPU) | Datos salen a Groq | System prompt, OpenAI-compatible | REST/SSE |
| **Llama 3.1 8B** 🟢 local | ‹med› | Alta | $0 · ~5–6 GB VRAM (Q4) | **Total (offline)** | System prompt, fine-tuning, GGUF | Ollama REST/streaming |
| **Mistral 7B** 🟢 local | ‹med› | Alta | $0 · ~4–5 GB | **Total** | Íd. | Ollama |
| **Phi-3.5** 🟢 local | ‹med› | Media-alta (muy eficiente) | $0 · ~2–3 GB | **Total** | Íd. | Ollama |
| **Gemma 2 9B** 🟢 local | ‹med› | Muy alta | $0 · ~6–7 GB | **Total** | Íd. | Ollama |
| **Qwen 2.5 7B** 🟢 local | ‹med› | Alta (multilingüe/código) | $0 · ~5–6 GB | **Total** | Íd. (buen soporte de tools) | Ollama |

> Incluir aquí la **Tabla LLM — latencia y velocidad** generada y la figura
> `figures/llm_ttft_vs_tps.png` (TTFT vs tokens/seg).

### Hallazgos
- **Latencia/velocidad:** _[redacte con sus datos: qué modelo dio menor TTFT y
  mayor throughput; correlación con el tamaño del modelo y el uso o no de GPU]._
- **Calidad:** Gemma 2 9B y Qwen 2.5 tienden a destacar en seguimiento de
  instrucciones complejas; Phi-3.5 ofrece el mejor compromiso calidad/recurso
  para hardware modesto. _[Respalde con los casos de `prompts_llm.json`, en
  especial la salida JSON estructurada y el razonamiento paso a paso.]_
- **Trade-off clave:** los modelos de 9B mejoran la calidad a costa de mayor
  VRAM y latencia; en CPU pura la diferencia de latencia se acentúa.

## 3.2 Reconocimiento de Voz (STT)

### Matriz comparativa (servicios × 6 dimensiones)

| Servicio (tipo) | 1. Latencia/RTF | 2. Precisión (WER) | 3. Costo/escala | 4. Privacidad | 5. Customización | 6. Integración |
|-----------------|-----------------|--------------------|-----------------|---------------|------------------|----------------|
| **Deepgram nova-2** 🟣 nube | ‹med› (muy bajo) | ‹med› (alta) | $200 crédito free; luego $/min | Datos salen a Deepgram | keywords, modelos, diarización | REST + WebSocket |
| **AssemblyAI** 🟣 nube | ‹med› | ‹med› (alta) | Free tier; luego $/h | Datos salen a AssemblyAI | word boost, modelos | REST (upload + polling) |
| **Groq Whisper large-v3** 🔵 nube | ‹med› (muy rápido) | ‹med› (muy alta) | Free tier | Datos salen a Groq | idioma, prompt inicial | REST OpenAI-compatible |
| **faster-whisper** 🟢 local | ‹med› | ‹med› (muy buena) | $0 · CPU/GPU, int8 | **Total (offline)** | tamaños, idioma, `initial_prompt` | Python (CTranslate2) |
| **openai-whisper** 🟢 local | ‹med› | ‹med› | $0 · más pesado en CPU | **Total** | tamaños/idioma | Python |
| **whisper.cpp** 🟢 local | ‹med› | ‹med› | $0 · óptimo en CPU (C++) | **Total** | cuantización GGML | binario CLI |
| **Vosk** 🟢 local | ‹med› (muy bajo) | ‹med› (menor) | $0 · ultraligero (~50 MB) | **Total** | gramáticas/vocabulario | Python streaming |
| **wav2vec2 (HF)** 🟢 local | ‹med› | ‹med› | $0 · requiere PyTorch | **Total** | fine-tuning CTC | `transformers` |

> Incluir la **Tabla STT — latencia y precisión** y la figura
> `figures/stt_latencia_vs_wer.png`.

### Hallazgos
- **Precisión vs velocidad:** la familia Whisper suele dominar el WER en
  español; Vosk sacrifica precisión a cambio de la **menor latencia y huella**,
  ideal para tiempo real en hardware limitado. _[Confirme con su WER medido.]_
- **faster-whisper** (CTranslate2, `int8`) tiende a ofrecer el mejor balance
  precisión/latencia; **whisper.cpp** es preferible cuando solo hay CPU.
- **wav2vec2** depende fuertemente del checkpoint en español y del preprocesado;
  reporte su comportamiento real frente a Whisper.

## 3.3 Síntesis de Voz (TTS)

### Matriz comparativa (servicios × 6 dimensiones)

| Servicio (tipo) | 1. Latencia/RTF | 2. Calidad (naturalidad) | 3. Costo/escala | 4. Privacidad | 5. Customización | 6. Integración |
|-----------------|-----------------|--------------------------|-----------------|---------------|------------------|----------------|
| **ElevenLabs mult. v2** 🟣 nube | ‹med› | Muy alta | 10k chars/mes free; luego $/char | Datos salen a ElevenLabs | **clonación de voz**, estilos | REST + streaming |
| **ElevenLabs Flash v2.5** 🔵 nube | ‹med› (baja latencia) | Alta | Mismo free tier | Datos salen a ElevenLabs | voces, idioma (multilingüe) | REST + streaming |
| **Deepgram Aura 2** 🔵 nube | ‹med› (muy bajo) | Alta (orientado a inglés) | $200 crédito free | Datos salen a Deepgram | voces, formato de salida | REST + WebSocket |
| **Piper** 🟢 local | ‹med› (muy bajo) | Buena | $0 · CPU eficiente (ONNX) | **Total (offline)** | voces por modelo | CLI/subproceso |
| **Coqui XTTS v2** 🟢 local | ‹med› (alto) | Muy alta (clonación) | $0 · GPU recomendada | **Total** | **clonación de voz** + idioma | Python |
| **Kokoro** 🟢 local | ‹med› | Alta | $0 · ligero | **Total** | voces/idiomas | Python |
| **eSpeak-NG** 🟢 local | ‹med› (mínimo) | Baja (robótica) | $0 · trivial | **Total** | fonemas/SSML básico | CLI |
| **Bark** 🟢 local | ‹med› (muy alto) | Alta/expresiva | $0 · GPU, pesado | **Total** | *prompts* de voz | Python |

> Incluir la **Tabla TTS — latencia y RTF** y la figura
> `figures/tts_latencia_vs_rtf.png`. Adjunte la **valoración cualitativa** de
> naturalidad escuchando los audios de `tts_output/` (escala 1–5 por motor).

### Hallazgos
- **Piper** ofrece el mejor compromiso naturalidad/latencia en CPU (RTF ≪ 1),
  apto para interacción en tiempo real.
- **XTTS v2** alcanza la mayor naturalidad y permite **clonación de voz**, pero
  su latencia y requerimiento de GPU lo alejan del tiempo real estricto.
- **eSpeak-NG** es el *baseline* de máxima velocidad y mínima calidad; útil como
  cota inferior de referencia. **Bark** es expresivo pero el más lento.

\newpage

# Arquitectura y Pipeline de Comunicación

El diseño completo del flujo de datos —diagrama de flujo y diagrama de
secuencia UML en notación Mermaid, más la descripción conceptual paso a paso—
se documenta en `report/pipeline_diagram.md` y se resume a continuación.

El *pipeline* integra las tres categorías evaluadas: **Unity (captura de
audio) → STT → LLM → TTS → Unity (reproducción)**, orquestado por un servidor
local. Las decisiones de diseño orientadas a **minimizar la latencia percibida**
son: (1) transporte por **WebSocket** full-dúplex entre Unity y el orquestador;
(2) consumo del LLM en modo *streaming* para aprovechar el **TTFT** bajo; y
(3) **síntesis incremental**, enviando frases parciales al TTS conforme el LLM
las produce, solapando generación y vocalización. El banco de pruebas mide de
forma aislada las etapas STT, LLM y TTS para fundamentar empíricamente qué
combinación minimiza la latencia total del *pipeline*.

\newpage

# Recomendaciones según Contexto y Conclusión

Las siguientes recomendaciones contrastan **latencia y costo** frente a
**privacidad y personalización**, y deben ajustarse con los números empíricos
finales de su corrida.

### Escenario A — Privacidad estricta y presupuesto cero (on-premise)
Todo el *stack* evaluado satisface por diseño el requisito de soberanía de
datos. Combinación sugerida: **faster-whisper (STT) + Phi-3.5 o Mistral 7B
(LLM) + Piper (TTS)**. Ofrece operación 100 % offline, huella moderada y
latencia razonable sin GPU de gama alta. Ideal para instituciones con datos
sensibles (p.ej. trámites estudiantiles).

### Escenario B — Interactivo en tiempo real, baja latencia (CPU modesta)
Prioriza el TTFT y el RTF mínimo: **Vosk (STT) + Phi-3.5 (LLM) + Piper o
eSpeak-NG (TTS)**. Se sacrifica algo de precisión y naturalidad a cambio de la
menor latencia de extremo a extremo, adecuado para kioscos o demos en hardware
limitado.

### Escenario C — Máxima calidad de experiencia (con GPU, local)
Cuando se dispone de GPU y la latencia no es crítica: **faster-whisper
(modelo `medium/large`) + Gemma 2 9B o Qwen 2.5 (LLM) + Coqui XTTS v2 (TTS con
clonación de voz)**. Maximiza precisión de transcripción, calidad de
razonamiento y naturalidad/identidad de voz del agente, **sin que los datos
salgan de la institución**.

### Escenario D — Tiempo real en la nube, mínima latencia (sin GPU propia)
Cuando la prioridad es la **latencia más baja posible** y se acepta que los
datos salgan a un tercero: **Deepgram nova-2 (STT) + Gemini 2.5 Flash o Groq
Llama 3.3 70B (LLM, TTFT muy bajo) + ElevenLabs Flash v2.5 (TTS)**. Aprovecha la infraestructura del
proveedor (free tier) para una experiencia muy fluida sin hardware local
potente. **Contrapartida:** menor privacidad (datos en la nube) y dependencia de
conectividad y de los límites de la capa gratuita; inadecuado si el requisito de
soberanía de datos es estricto.

### Conclusión
El estudio demuestra que existe un **espectro de arquitecturas viables** para un
agente virtual por voz, desde una solución **100 % local, privada y de costo
operativo nulo** (Ollama + Whisper local + Piper) hasta una **basada en la nube
de mínima latencia** (Groq + Deepgram + ElevenLabs) sin hardware propio. La
selección óptima no es única: surge del balance que cada escenario exige entre
**latencia, calidad, costo y privacidad**. El hallazgo central es que la
soberanía de datos y la calidad de experiencia se ubican en extremos opuestos de
ese espacio de diseño, y la decisión correcta depende del contexto institucional.
Los datos empíricos recolectados con este banco de pruebas —reproducible vía
Docker— constituyen la base objetiva para esa decisión arquitectónica y para las
fases posteriores del desarrollo del agente.

\newpage

# Anexos

- **Código del banco de pruebas:** `benchmarks/`, `common/`, `analysis/`.
- **Datos crudos:** `results/*.csv` y `results/*.jsonl`.
- **Tablas y figuras generadas:** `report/tablas_generadas.md`,
  `report/figures/`.
- **Reproducibilidad:** `README.md`, `Dockerfile`, `docker-compose.yml`.

> _Recordatorio de calidad (rúbrica): revise la ortografía antes de exportar
> (penalización de 0.25 pts por falta) y verifique que ninguna credencial ni
> archivo `.env` se haya subido al repositorio._
