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
pruebas (*benchmarking*) sobre **quince servicios de código abierto y ejecución
estrictamente local (offline)**, distribuidos en tres categorías que componen
el *pipeline* de comunicación del agente: modelos de lenguaje (LLM),
reconocimiento de voz (STT) y síntesis de voz (TTS). La decisión de restringir
el estudio a soluciones locales responde a dos objetivos del proyecto: garantizar
**soberanía total de los datos** (presupuesto cero en APIs y privacidad máxima)
y producir un banco de pruebas **reproducible** en una máquina limpia mediante
contenedores Docker.

## Objetivos específicos

1. Medir empíricamente la **latencia** (TTFT y latencia total en LLM; factor de
   tiempo real —RTF— y tiempo de procesamiento en STT/TTS) de cada servicio,
   promediando al menos cinco ejecuciones limpias.
2. Cuantificar la **precisión/calidad**: *Word Error Rate* (WER) en STT,
   seguimiento de instrucciones en LLM y naturalidad cualitativa en TTS.
3. Analizar **costo y escalabilidad** en términos de infraestructura local
   (VRAM, RAM, consumo) al no existir costo por token o por minuto.
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

| Categoría | Servicios (5 por categoría) | Tipo |
|-----------|------------------------------|------|
| **LLM** | Llama 3.1 8B, Mistral 7B, Phi-3.5, Gemma 2 9B, Qwen 2.5 7B | Open-weights vía Ollama |
| **STT** | faster-whisper, openai-whisper, whisper.cpp, Vosk, wav2vec2 | Open-source local |
| **TTS** | Piper, Coqui XTTS v2, Kokoro, eSpeak-NG, Bark | Open-source local |

La muestra incluye el balance exigido: modelos de mayor capacidad (Gemma 2 9B,
XTTS v2, Whisper), opciones optimizadas para velocidad/bajo recurso (Phi-3.5,
Vosk, Piper, eSpeak-NG) y, por definición, despliegue 100 % offline.

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

### Matriz comparativa (5 modelos × 6 dimensiones)

| Dimensión | Llama 3.1 8B | Mistral 7B | Phi-3.5 | Gemma 2 9B | Qwen 2.5 7B |
|-----------|--------------|-----------|---------|------------|-------------|
| **1. Latencia** (TTFT / total) | ‹med›/‹med› | ‹med› | ‹med› | ‹med› | ‹med› |
| **2. Calidad** (instrucciones/JSON) | Alta | Alta | Media-alta | Muy alta | Alta (fuerte en multilingüe/código) |
| **3. Costo/escala** | $0 API · ~5–6 GB VRAM (Q4) | $0 · ~4–5 GB | $0 · ~2–3 GB (más ligero) | $0 · ~6–7 GB | $0 · ~5–6 GB |
| **4. Privacidad** | Total (offline) | Total | Total | Total | Total |
| **5. Customización** | System prompt, fine-tuning, GGUF | Íd. | Íd. | Íd. | Íd. (buen soporte de herramientas) |
| **6. Integración** | API Ollama REST/streaming | Íd. | Íd. | Íd. | Íd. |

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

### Matriz comparativa (5 motores × 6 dimensiones)

| Dimensión | faster-whisper | openai-whisper | whisper.cpp | Vosk | wav2vec2 (HF) |
|-----------|----------------|----------------|-------------|------|----------------|
| **1. Latencia/RTF** | ‹med› | ‹med› | ‹med› | ‹med› (muy bajo) | ‹med› |
| **2. Precisión** (WER) | ‹med› (muy buena) | ‹med› | ‹med› | ‹med› (menor) | ‹med› |
| **3. Costo/escala** | $0 · CPU/GPU, int8 eficiente | $0 · más pesado en CPU | $0 · óptimo en CPU (C++) | $0 · ultraligero (~50 MB) | $0 · requiere PyTorch |
| **4. Privacidad** | Total (offline) | Total | Total | Total | Total |
| **5. Customización** | tamaños de modelo, idioma, `initial_prompt` | tamaños/idioma | cuantización GGML | gramáticas/vocabulario | fine-tuning CTC |
| **6. Integración** | API Python (CTranslate2) | API Python | binario CLI/subproceso | API Python streaming | `transformers` |

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

### Matriz comparativa (5 motores × 6 dimensiones)

| Dimensión | Piper | Coqui XTTS v2 | Kokoro | eSpeak-NG | Bark |
|-----------|-------|---------------|--------|-----------|------|
| **1. Latencia/RTF** | ‹med› (muy bajo) | ‹med› (alto) | ‹med› | ‹med› (mínimo) | ‹med› (muy alto) |
| **2. Calidad** (naturalidad) | Buena | Muy alta (clonación) | Alta | Baja (robótica) | Alta/expresiva |
| **3. Costo/escala** | $0 · CPU eficiente (ONNX) | $0 · GPU recomendada | $0 · ligero | $0 · trivial | $0 · GPU, pesado |
| **4. Privacidad** | Total (offline) | Total | Total | Total | Total |
| **5. Customización** | voces por modelo | **clonación de voz** + idioma | voces/idiomas | fonemas/SSML básico | *prompts* de voz |
| **6. Integración** | CLI/subproceso | API Python | API Python | CLI | API Python |

> Incluir la **Tabla TTS — latencia y RTF** y la figura
> `figures/tts_latencia_vs_rtf.png`. Adjunte la **valoración cualitativa** de
> naturalidad escuchando los WAV de `tts_output/` (escala 1–5 por motor).

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

### Escenario C — Máxima calidad de experiencia (con GPU)
Cuando se dispone de GPU y la latencia no es crítica: **faster-whisper
(modelo `medium/large`) + Gemma 2 9B o Qwen 2.5 (LLM) + Coqui XTTS v2 (TTS con
clonación de voz)**. Maximiza precisión de transcripción, calidad de
razonamiento y naturalidad/identidad de voz del agente.

### Conclusión
El estudio demuestra que es viable construir un agente virtual por voz
**completo, privado y de costo operativo nulo** empleando exclusivamente
software de código abierto local. La selección óptima no es única: depende del
balance que cada escenario exige entre latencia, calidad y recursos de
hardware. Los datos empíricos recolectados con este banco de pruebas
—reproducible vía Docker— constituyen la base objetiva para esa decisión
arquitectónica y para las fases posteriores del desarrollo del agente.

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
