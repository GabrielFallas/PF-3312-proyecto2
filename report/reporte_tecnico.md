---
title: "Benchmarking de Servicios de IA para Agentes Virtuales Inteligentes"
subtitle: "Proyecto 2 — Laboratorio PF-3312, Universidad de Costa Rica"
author: "Gabriel Fallas Mora"
date: "I Ciclo 2026"
lang: es
toc: true
toc-depth: 2
numbersections: true
geometry: margin=2.5cm
---

\newpage

# Introducción y Objetivos

El desarrollo de un agente virtual interactivo capaz de conversar por voz exige
seleccionar una arquitectura de servicios cognitivos que equilibre desempeño,
costo, privacidad y facilidad de integración. La elección no puede sustentarse
en la popularidad comercial de una API ni en el tamaño nominal de un modelo:
requiere **evidencia empírica** recolectada bajo condiciones controladas y
reproducibles.

Este reporte documenta el diseño, la ejecución y el análisis de un banco de
pruebas (*benchmarking*) sobre **veinte servicios** distribuidos en tres
categorías que componen el *pipeline* de comunicación del agente: modelos de
lenguaje (LLM), reconocimiento de voz (*Speech-to-Text*, STT) y síntesis de voz
(*Text-to-Speech*, TTS). La muestra mantiene el **balance representativo** que
exige el enunciado, combinando en cada categoría tres tipos de proveedor:

1. **Modelos comerciales de alta gama en la nube** (p. ej. Gemini 2.5 Pro,
   gpt-oss-120B y Llama 4 Scout servidos en Groq, Deepgram nova-2, AssemblyAI,
   ElevenLabs multilingual v2).
2. **APIs comerciales de bajo costo o alta velocidad** (Gemini 2.5 Flash-Lite,
   Groq Llama 3.3 70B, Groq Whisper large-v3, ElevenLabs Flash v2.5,
   Deepgram Aura 2).
3. **Modelos de código abierto de despliegue estrictamente local y offline**
   (Ollama: Llama 3.1, Mistral, Phi-3.5, Gemma 2, Qwen 2.5; faster-whisper,
   Vosk; Piper).

Para no incurrir en costos, los servicios en la nube se consumen a través de sus
**capas gratuitas (*free tier*)**. Esta combinación permite contrastar de forma
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

# Marco de Referencia y Trabajo Relacionado

El benchmarking de servicios cognitivos se apoya en un cuerpo creciente de
literatura técnica que define las métricas y las buenas prácticas adoptadas en
este trabajo. Esta sección sitúa el proyecto en ese contexto.

## Métricas de latencia en LLM

La literatura de *serving* de modelos de lenguaje ha consolidado el **Time To
First Token (TTFT)** como la métrica primordial de responsividad percibida: mide
el tiempo entre la recepción del *prompt* y la emisión del primer token, y
refleja la fase de *prefill* del modelo [1, 2]. Estudios como *LLM-Inference-Bench*
[1] y los trabajos sobre meta-métricas y evaluación de sistemas de *serving*
[2, 3] subrayan que, en aplicaciones interactivas, el TTFT y la *Inter-Token
Latency* (ITL, o su inverso, tokens/seg) son más informativos que la latencia
total agregada, porque determinan la sensación de inmediatez. Este proyecto
adopta exactamente esa distinción: se reporta TTFT, latencia total y tokens/seg
medidos en modo *streaming*, en lugar de las cifras teóricas publicadas por los
proveedores.

## Reconocimiento de voz (STT) y WER

El modelo *Whisper* [4], entrenado con supervisión débil a gran escala, fijó el
estándar de referencia para reconocimiento multilingüe y popularizó el uso del
**Word Error Rate (WER)** sobre corpus como Common Voice y FLEURS. Trabajos
posteriores como *MMS* (*Scaling Speech Technology to 1,000+ Languages*) [5]
muestran que el WER varía drásticamente según el idioma y la calidad del audio,
y advierten que el desempeño sobre datos reales con ruido es notablemente peor
que sobre corpus académicos limpios. Este hallazgo es directamente pertinente a
nuestra metodología (ver §4.2): al evaluar sobre voz sintética limpia, los WER
obtenidos son un piso optimista, y la diferenciación práctica se traslada a la
latencia.

## Síntesis de voz (TTS): naturalidad y RTF

La calidad de un sistema TTS se evalúa tradicionalmente con el **Mean Opinion
Score (MOS)**, una valoración subjetiva en escala 1–5 recopilada de múltiples
oyentes; conjuntos como *SOMOS* [6] y objetivos como *NaturalSpeech* [7] formalizan
este protocolo y la meta de "calidad a nivel humano". Para la eficiencia se usa
el **Real-Time Factor (RTF)**, definido como el cociente entre el tiempo de
síntesis y la duración del audio producido; un RTF < 1 indica síntesis más rápida
que el tiempo real [8]. Dado que un MOS riguroso requiere un panel de oyentes
fuera del alcance de este proyecto individual, aquí se reporta una **valoración
cualitativa de naturalidad** complementada con el RTF empírico, siguiendo la
práctica de los estudios de responsividad de TTS de código abierto [8].

## Arquitecturas de agentes de voz en tiempo real

La industria converge en el patrón encadenado **STT → LLM → TTS** como base de
los agentes de voz [9]. La literatura aplicada coincide en que la conversación
humana opera en una ventana de respuesta de **300–500 ms**, y que retardos
superiores a **500–700 ms** comienzan a percibirse como antinaturales [9]. Un
*pipeline* secuencial ingenuo acumula 2–4 s de latencia; la solución es el
**procesamiento en flujo (*streaming*)**: transcripción parcial incremental,
consumo del LLM token a token y **síntesis incremental** de frases conforme se
generan, solapando etapas. Estas referencias fundamentan las decisiones de
diseño del *pipeline* propuesto en §5 y los umbrales con que se interpretan los
resultados de latencia.

## Panorama de modelos vigente (2026)

La selección de modelos locales se alineó con el estado del arte de modelos
*open-weight* ejecutables en hardware de consumo: las familias **Llama 3.x**,
**Qwen 2.5/3**, **Phi** (Microsoft) y **Gemma 2** (Google) dominan el segmento de
7–14 B parámetros, ofreciendo un equilibrio calidad/recurso adecuado para una
sola GPU [10]. En la nube se incluyen modelos *flagship* recientes —**gpt-oss-120B**
(OpenAI, pesos abiertos, 120 B) y **Llama 4 Scout** (Meta)— servidos sobre la
arquitectura LPU de Groq, además de **Gemini 2.5** (Google). Esta cobertura
asegura que las conclusiones reflejen tecnología vigente y no modelos obsoletos.

\newpage

# Metodología de Pruebas

## Entorno de ejecución

Los benchmarks se ejecutaron sobre el siguiente entorno real:

| Componente | Especificación |
|------------|----------------|
| CPU | Intel Core i7-13700KF (16 núcleos / 24 hilos) |
| GPU | NVIDIA GeForce RTX 5070 Ti, 16 GB VRAM (driver 596.49) |
| RAM | 32 GB |
| Sistema operativo | Windows 11 Pro |
| Runtime de contenedores | Docker Engine 29.5.2 + Compose v2 |
| Servidor LLM local | Ollama (`ollama/ollama:latest`) con aceleración **GPU** (CUDA) |
| STT/TTS locales | Python 3.12 en `venv`, ejecución en **CPU** (`int8`) |
| Red | Servicios en la nube consumidos por API REST desde la misma máquina |

Todo el banco de pruebas se ejecuta de forma **contenerizada**: un contenedor
sirve los LLM (Ollama, con paso de GPU mediante el *runtime* `nvidia`) y otro
ejecuta los scripts de medición, comunicándose por la red interna de Docker
Compose. Esto elimina diferencias de entorno y permite reconstruir el experimento
con tres comandos (ver `README.md`).

## Servicios evaluados (20 servicios; balance de tres tipos)

La muestra cumple el **balance representativo** exigido por el enunciado y supera
el mínimo de 5 servicios por categoría. Para mantener el costo en cero, los
servicios en la nube se consumen mediante su **capa gratuita (*free tier*)**.

| Categoría | Nube — alta gama | Nube — bajo costo/rápido | Local — offline |
|-----------|------------------|--------------------------|-----------------|
| **LLM** (10) | Gemini 2.5 Pro¹; **gpt-oss-120B**, **Llama 4 Scout** (Groq) | Gemini 2.5 Flash²; Gemini 2.5 Flash-Lite; Groq Llama 3.3 70B | Llama 3.1 8B, Mistral 7B, Phi-3.5, Gemma 2 9B, Qwen 2.5 7B |
| **STT** (5) | Deepgram nova-2; AssemblyAI | Groq Whisper large-v3 | faster-whisper, Vosk |
| **TTS** (5) | ElevenLabs multilingual v2 | ElevenLabs Flash v2.5; Deepgram Aura 2 | Piper es-ES, Piper es-MX |

¹ **Nota sobre Gemini 2.5 Pro (hallazgo de costo/gobernanza).** El modelo
*flagship* de razonamiento de Google se incluyó en el catálogo como referencia de
gama alta, pero **su capa gratuita devuelve sistemáticamente HTTP 429
(*Too Many Requests*) desde la primera petición**, incluso con tope de tokens y
presupuesto de razonamiento mínimo (`thinkingBudget = 128`). En la práctica,
Gemini 2.5 Pro **no es utilizable sin facturación activa**, lo que constituye en
sí mismo un dato relevante de viabilidad financiera. Por ello, el punto de
referencia empírico de "alta gama en la nube" lo aportan **gpt-oss-120B (120 B,
pesos abiertos de OpenAI)** y **Llama 4 Scout**, modelos *flagship* servidos sobre
la LPU de Groq con *free tier* real.

² Gemini 2.5 Flash pertenece a la familia *flagship* de Google y, con su *free
tier* más generoso, se sitúa entre la alta gama y el bajo costo; se reporta como
alta gama por capacidad de razonamiento y como contraste de latencia.

Se descartan **OpenAI, Anthropic y Azure** por carecer de un acceso gratuito
práctico para este ejercicio. Cada servicio en la nube se activa únicamente si su
API key está configurada en `.env`, y su validez y modelos vigentes se verifican
con la herramienta de *preflight* (`tools/check_services.py`) mediante endpoints
de solo lectura, **sin consumir cuota de uso**. Los scripts soportan además otros
motores locales (openai-whisper, whisper.cpp, wav2vec2; Coqui XTTS v2, Kokoro,
eSpeak-NG, Bark) reproducibles con un comando.

## Insumos de prueba controlados

- **LLM** — `data/prompts_llm.json`: cinco *prompts* que ejercitan razonamiento
  aritmético, seguimiento estricto de instrucciones, salida estructurada (JSON),
  conocimiento de dominio y robustez multilingüe, todos bajo un mismo *System
  Prompt* que fija la persona del agente ("Aurora").
- **STT** — un audio en español de 16 kHz mono (`data/audio/muestra_es.wav`) con
  su transcripción de referencia (`data/reference_transcript.txt`) para el cálculo
  de WER. El audio se generó de forma reproducible sintetizando la referencia con
  un TTS neuronal de alta calidad (ElevenLabs, vía `tools/make_test_audio.py`),
  garantizando una correspondencia exacta texto–audio. **Implicación
  metodológica:** al ser voz sintética limpia (sin ruido ni acentos espontáneos),
  los motores STT de buena calidad alcanzan un WER cercano a 0 %, por lo que en
  este material la diferenciación se da principalmente en la **latencia**; un
  audio real con ruido ambiental ampliaría las diferencias de WER, en línea con
  lo reportado por la literatura [5] (ver Recomendaciones y trabajo futuro).
- **TTS** — un párrafo representativo del dominio (`data/tts_text_es.txt`).

## Herramientas y protocolo de medición

- **Cronometraje:** `time.perf_counter()` (reloj monótono de alta resolución). En
  LLM se consume la API en modo *streaming*: el primer fragmento con contenido
  marca el **TTFT** y el evento de cierre delimita la latencia total; se registra
  además `tokens/seg`.
- **Calidad:** WER con la librería `jiwer` (con respaldo propio de Levenshtein por
  palabras) sobre texto normalizado; **RTF = tiempo de procesamiento / duración
  del audio** para STT y TTS.
- **Repeticiones:** `N_RUNS = 5` ejecuciones por prueba **más una corrida de
  calentamiento que se descarta** (mitiga el sesgo de carga inicial de modelo y
  cachés). Temperatura del LLM fijada en `0.0` para reproducibilidad.
- **Conservación de cuota:** los servicios en la nube aplican un tope de tokens de
  salida (`CLOUD_MAX_OUTPUT_TOKENS`) y una pausa entre peticiones
  (`CLOUD_REQUEST_DELAY`) que **no afecta la medición** (se aplica tras cronometrar
  cada corrida), para no agotar las capas gratuitas.
- **Persistencia y seguridad:** cada ejecución se anexa a `results/*.csv` (formato
  largo). Una rutina de redacción (`common/persistence.redact`) enmascara
  cualquier patrón de API key antes de escribir a disco, como red de seguridad
  contra fugas de credenciales. El script `analysis/build_report_data.py`
  consolida promedios y genera las tablas y figuras de este reporte.

\newpage

# Análisis Comparativo por Categoría

Todas las cifras de esta sección son **empíricas**, medidas con los scripts del
repositorio (promedio de 5 corridas, descartando una de calentamiento) y
consolidadas con `analysis/build_report_data.py`. Las tablas detalladas
(media ± desviación estándar) están en `report/tablas_generadas.md`.

## Modelos de Lenguaje (LLM)

### Matriz comparativa (servicios × 6 dimensiones)

_Latencia en formato TTFT / total (s), media de 5 corridas. Valores empíricos
medidos en el entorno descrito (LLM locales en GPU RTX 5070 Ti; nube vía free tier)._

| Servicio (tipo) | 1. Latencia TTFT/total (s) | 2. Velocidad (tok/s) | 3. Costo/escala | 4. Privacidad | 5. Customización | 6. Integración |
|-----------------|----------------------------|----------------------|-----------------|---------------|------------------|----------------|
| **Gemini 2.5 Pro** 🟣 nube alta gama | — (HTTP 429 sin facturación) | — | Sin *free tier* usable; $/1M tokens | Datos salen a Google | System instruction, *tools*, JSON | REST/SSE |
| **gpt-oss-120B (Groq)** 🟣 nube alta gama | 0.66 / 0.93 | **196** | Free tier; luego $/1M tokens (LPU) | Datos salen a Groq | System prompt (OpenAI-compat), JSON | REST/SSE |
| **Llama 4 Scout (Groq)** 🟣 nube alta gama | 0.62 / 0.85 | 111 | Free tier; luego $/1M tokens | Datos salen a Groq | System prompt (OpenAI-compat) | REST/SSE |
| **Gemini 2.5 Flash** 🟣 nube | 1.79 / 1.89 | 20 | Free tier; luego $/1M tokens | Datos salen a Google | System instruction, *tools*, JSON | REST/SSE |
| **Gemini 2.5 Flash-Lite** 🔵 nube | 0.67 / 0.95 | 100 | Free tier amplio | Datos salen a Google | Íd. | REST/SSE |
| **Groq Llama 3.3 70B** 🔵 nube | 0.40 / 0.73 | 140 | Free tier; LPU muy rápida | Datos salen a Groq | System prompt (OpenAI-compat) | REST/SSE |
| **Llama 3.1 8B** 🟢 local | 0.11 / 0.90 | 142 | $0 · ~5 GB VRAM (Q4) | **Total (offline)** | System prompt, *fine-tuning*, GGUF | Ollama REST/streaming |
| **Mistral 7B** 🟢 local | 0.03 / 0.86 | 150 | $0 · ~4–5 GB | **Total** | Íd. | Ollama |
| **Phi-3.5** 🟢 local | 0.03 / 0.60 | **257** | $0 · ~2–3 GB | **Total** | Íd. | Ollama |
| **Gemma 2 9B** 🟢 local | 0.10 / 1.02 | 115 | $0 · ~6–7 GB | **Total** | Íd. | Ollama |
| **Qwen 2.5 7B** 🟢 local | 0.09 / 0.62 | 155 | $0 · ~5 GB | **Total** | Íd. (buen soporte de *tools*) | Ollama |

![LLM: TTFT vs velocidad de generación](figures/llm_ttft_vs_tps.png)

### Hallazgos

- **El TTFT local en GPU es de otro orden de magnitud.** Los modelos locales
  (Phi-3.5 y Mistral con TTFT ≈ 0,03 s; Llama/Gemma/Qwen ≈ 0,09–0,11 s) responden
  el primer token **10–50× más rápido** que Gemini 2.5 Flash (1,79 s), porque
  evitan el viaje de red. Para una conversación por voz —donde el TTFT define la
  sensación de inmediatez [1, 9]— esto es decisivo: los locales se ubican dentro
  de la ventana conversacional de 300–500 ms, mientras Gemini Flash la excede.
- **La alta gama accesible en la nube es muy competitiva en velocidad.**
  gpt-oss-120B alcanzó **196 tok/s** —la mayor velocidad de generación de toda la
  muestra en la nube, superando incluso a varios locales— gracias a la LPU de
  Groq, con TTFT de 0,66 s. Llama 4 Scout (111 tok/s) y Groq Llama 3.3 70B (140
  tok/s) confirman que la LPU compensa parcialmente la latencia de red. Aun así,
  su TTFT (0,6–0,7 s) sigue siendo ~6–20× mayor que el de un modelo local en GPU.
- **El verdadero *flagship* de razonamiento (Gemini 2.5 Pro) es inaccesible sin
  pago.** Su capa gratuita devolvió HTTP 429 en todas las pruebas; el dato es
  relevante para la decisión arquitectónica: la máxima gama propietaria implica
  costo financiero ineludible y dependencia de facturación.
- **Velocidad de generación local:** Phi-3.5 lidera con **257 tok/s**, seguido de
  Qwen 2.5 (155), Mistral (150) y Llama 3.1 (142). Gemini 2.5 Flash resultó el más
  lento (20 tok/s), comportándose como un modelo de mayor "deliberación".
- **Trade-off nube vs local:** con una GPU de gama media (RTX 5070 Ti, 16 GB) los
  modelos locales **igualan o superan** a las APIs en la nube en latencia, a costo
  cero y con privacidad total. La nube aporta valor cuando no se dispone de GPU
  (gpt-oss-120B, Groq y Flash-Lite siguen siendo muy rápidos) o cuando se requiere
  la máxima calidad de razonamiento de un *flagship* propietario.
- **Calidad (cualitativa sobre `prompts_llm.json`):** gpt-oss-120B y Llama 4 Scout
  ofrecieron las respuestas más completas y mejor estructuradas; entre los locales,
  Gemma 2 9B y Qwen 2.5 destacaron en seguimiento de instrucciones y salida JSON;
  Phi-3.5 ofrece el mejor compromiso calidad/recurso (2–3 GB de VRAM).

## Reconocimiento de Voz (STT)

### Matriz comparativa (servicios × 6 dimensiones)

_Latencia total (s) y RTF medidos sobre un audio de 18,2 s; media de 5 corridas.
Motores locales en CPU._

| Servicio (tipo) | 1. Latencia (s) / RTF | 2. Precisión (WER) | 3. Costo/escala | 4. Privacidad | 5. Customización | 6. Integración |
|-----------------|-----------------------|--------------------|-----------------|---------------|------------------|----------------|
| **Deepgram nova-2** 🟣 nube alta gama | 1.50 / 0.08 | 0.0 % | $200 crédito free; luego $/min | Datos salen a Deepgram | *keywords*, diarización | REST + WebSocket |
| **AssemblyAI** 🟣 nube alta gama | 5.70 / 0.31 | 0.0 % | Free tier; luego $/h | Datos salen a AssemblyAI | *word boost*, modelos | REST (upload + polling) |
| **Groq Whisper large-v3** 🔵 nube | 2.48 / 0.14 | 0.0 % | Free tier | Datos salen a Groq | idioma, *prompt* inicial | REST OpenAI-compatible |
| **faster-whisper (base)** 🟢 local | **0.91 / 0.05** | 0.0 % | $0 · CPU int8 | **Total (offline)** | tamaños, idioma, `initial_prompt` | Python (CTranslate2) |
| **Vosk (es small)** 🟢 local | 0.96 / 0.05 | 0.0 % | $0 · ultraligero (~50 MB) | **Total** | gramáticas/vocabulario | Python streaming |

![STT: latencia vs WER](figures/stt_latencia_vs_wer.png)

### Hallazgos

- **WER ≈ 0 % en todos los motores** sobre el audio sintético limpio, por lo que
  la diferenciación práctica se dio en la **latencia** (ver nota metodológica y
  [5]). Sobre audio real con ruido, la literatura predice que aparecerían brechas
  de WER, favorables a Whisper large-v3 y a los motores de la nube de alta gama.
- **Los motores locales en CPU fueron los más rápidos:** faster-whisper (0,91 s,
  RTF 0,05) y Vosk (0,96 s) superaron incluso a la nube, al evitar la subida del
  audio. faster-whisper ofrece el mejor balance precisión/latencia/peso.
- **En la nube**, Deepgram nova-2 (1,50 s) fue claramente el más rápido; Groq
  Whisper (2,48 s) quedó intermedio y **AssemblyAI (5,70 s)** resultó el más lento
  por su flujo de *upload + polling* asíncrono, penalizado en archivos cortos.

## Síntesis de Voz (TTS)

### Matriz comparativa (servicios × 6 dimensiones)

_Latencia de síntesis (s) y RTF para un texto de ~210 caracteres; media de 5
corridas. Motores locales en CPU._

| Servicio (tipo) | 1. Latencia (s) / RTF | 2. Calidad (naturalidad) | 3. Costo/escala | 4. Privacidad | 5. Customización | 6. Integración |
|-----------------|-----------------------|--------------------------|-----------------|---------------|------------------|----------------|
| **ElevenLabs mult. v2** 🟣 nube alta gama | 2.16 / 0.17 | Muy alta | 10k chars/mes free; luego $/char | Datos salen a ElevenLabs | **clonación de voz**, estilos | REST + streaming |
| **ElevenLabs Flash v2.5** 🔵 nube | **1.20 / 0.09** | Alta | Mismo free tier | Datos salen a ElevenLabs | voces, idioma (multilingüe) | REST + streaming |
| **Deepgram Aura 2 (es)** 🔵 nube | 6.89 / 0.49 | Alta | $200 crédito free | Datos salen a Deepgram | voces, formato de salida | REST + WebSocket |
| **Piper es-ES (davefx)** 🟢 local | 1.76 / 0.15 | Buena | $0 · CPU eficiente (ONNX) | **Total (offline)** | voces por modelo | CLI/subproceso |
| **Piper es-MX (claude, high)** 🟢 local | 1.50 / 0.11 | Buena+ | $0 · CPU eficiente (ONNX) | **Total** | voces por modelo | CLI/subproceso |

![TTS: latencia vs RTF](figures/tts_latencia_vs_rtf.png)

### Hallazgos

- **Todos los motores operan muy por debajo de tiempo real (RTF < 0,5).** El más
  rápido fue **ElevenLabs Flash v2.5** (1,20 s, RTF 0,09), seguido de Piper es-MX
  (1,50 s) y es-ES (1,76 s) **en CPU**, lo que confirma a Piper como excelente
  opción local de baja latencia.
- **ElevenLabs multilingual v2** (2,16 s) entrega la mayor naturalidad y clonación
  de voz, a costa de algo más de latencia que su variante Flash.
- **Deepgram Aura 2** en español resultó el **más lento** (6,89 s, RTF 0,49),
  contrario a su perfil "rápido" en inglés; su voz española aún es menos madura.
- **Naturalidad (valoración cualitativa, audios en `tts_output/`):** ElevenLabs >
  Piper > Deepgram Aura(es), en una escucha informal; ElevenLabs suena claramente
  más natural, Piper es muy inteligible con prosodia algo más plana. Una
  evaluación MOS formal con panel de oyentes [6, 7] queda como trabajo futuro.

\newpage

# Arquitectura y Pipeline de Comunicación

El diseño completo del flujo de datos —diagrama de flujo y diagrama de secuencia
UML en notación Mermaid, más la descripción conceptual paso a paso— se documenta
en `report/pipeline_diagram.md` y se resume a continuación.

El *pipeline* integra las tres categorías evaluadas: **Unity (captura de audio)
→ STT → LLM → TTS → Unity (reproducción)**, orquestado por un servidor local.
Las decisiones de diseño orientadas a **minimizar la latencia percibida**, y
respaldadas por los datos de §4 y la literatura [9], son:

1. **Transporte por WebSocket full-dúplex** entre Unity y el orquestador, para
   *streaming* bidireccional de audio y eventos de turno (*turn-taking*, *barge-in*).
2. **Consumo del LLM en modo *streaming***, aprovechando el TTFT bajo: el primer
   token dispara de inmediato la síntesis, en lugar de esperar la respuesta
   completa.
3. **Síntesis incremental**: se envían frases parciales al TTS conforme el LLM las
   produce, solapando generación y vocalización para reducir la latencia de
   extremo a extremo por debajo del umbral conversacional.

El banco de pruebas mide de forma aislada las etapas STT, LLM y TTS para
fundamentar empíricamente qué combinación minimiza la latencia total del
*pipeline*. Sumando los mejores tiempos locales medidos (faster-whisper 0,91 s +
TTFT de Phi-3.5 0,03 s + primera frase de Piper ≈ 0,3 s) se obtiene una latencia
percibida de **primer audio** muy inferior a 1,5 s sin salir de la máquina, lo que
valida la viabilidad de un agente privado y responsivo.

\newpage

# Recomendaciones según Contexto y Conclusión

Las siguientes recomendaciones contrastan **latencia y costo** frente a
**privacidad y personalización**, fundamentadas en los datos empíricos de §4.

### Escenario A — Privacidad estricta y presupuesto cero (on-premise)
Todo el *stack* local evaluado satisface por diseño la soberanía de datos.
Combinación sugerida: **faster-whisper (STT) + Phi-3.5 o Mistral 7B (LLM) + Piper
(TTS)**. Operación 100 % offline, huella moderada y latencia razonable sin GPU de
gama alta. Ideal para instituciones con datos sensibles (p. ej. trámites
estudiantiles). El TTFT de 0,03 s del LLM local es insuperable por cualquier API.

### Escenario B — Interactivo en tiempo real, baja latencia (CPU modesta)
Prioriza el TTFT y el RTF mínimo: **Vosk (STT) + Phi-3.5 (LLM) + Piper o eSpeak-NG
(TTS)**. Se sacrifica algo de precisión y naturalidad a cambio de la menor latencia
de extremo a extremo, adecuado para kioscos o demos en hardware limitado.

### Escenario C — Máxima calidad de experiencia (con GPU, local)
Cuando se dispone de GPU y la latencia no es crítica: **faster-whisper
(`medium/large`) + Gemma 2 9B o Qwen 2.5 (LLM) + Coqui XTTS v2 (TTS con clonación
de voz)**. Maximiza precisión de transcripción, calidad de razonamiento y
naturalidad/identidad de voz del agente, **sin que los datos salgan de la
institución**.

### Escenario D — Tiempo real en la nube, mínima latencia (sin GPU propia)
Cuando la prioridad es la **latencia más baja posible sin hardware local** y se
acepta que los datos salgan a un tercero: **Deepgram nova-2 (STT) + gpt-oss-120B o
Groq Llama 3.3 70B (LLM, alta velocidad en LPU) + ElevenLabs Flash v2.5 (TTS)**.
Aprovecha la infraestructura del proveedor (free tier) para una experiencia muy
fluida; gpt-oss-120B aporta calidad *flagship* a 196 tok/s. **Contrapartida:**
menor privacidad, dependencia de conectividad y de los límites de la capa gratuita.

### Escenario E — Máxima calidad de razonamiento propietario (presupuesto disponible)
Si el caso de uso exige el mejor razonamiento comercial y hay presupuesto:
**Gemini 2.5 Pro** (con facturación activa, pues su *free tier* es inviable) sobre
una base STT/TTS de la nube. Se acepta el costo por token y la dependencia total
del proveedor a cambio de la capacidad de la gama más alta. Este escenario solo se
justifica cuando la calidad de razonamiento prima sobre costo, latencia y privacidad.

### Conclusión

El estudio demuestra que existe un **espectro de arquitecturas viables** para un
agente virtual por voz, desde una solución **100 % local, privada y de costo
operativo nulo** (Ollama + Whisper local + Piper) hasta una **basada en la nube de
mínima latencia** (gpt-oss-120B / Groq + Deepgram + ElevenLabs) sin hardware
propio. La selección óptima no es única: surge del balance que cada escenario
exige entre **latencia, calidad, costo y privacidad**.

El hallazgo central es que la **soberanía de datos y la calidad de experiencia se
ubican en extremos de un mismo espacio de diseño**, pero la brecha es menor de lo
que sugiere el marketing: una GPU de gama media iguala o supera a la nube en
latencia, y los *flagships* de pesos abiertos (gpt-oss-120B) ofrecen calidad de
gama alta sin el costo ineludible del *flagship* propietario (Gemini 2.5 Pro, cuyo
*free tier* resultó inviable). Los datos empíricos recolectados con este banco de
pruebas —reproducible vía Docker— constituyen la base objetiva para la decisión
arquitectónica y para las fases posteriores del desarrollo del agente.

\newpage

# Referencias

[1] Bhandare, A. et al. (2024). *LLM-Inference-Bench: Inference Benchmarking of
Large Language Models on AI Accelerators*. arXiv:2411.00136.
<https://arxiv.org/abs/2411.00136>

[2] *Meta-Metrics and Best Practices for System-Level Inference Performance
Benchmarking* (2025). arXiv:2508.10251. <https://arxiv.org/abs/2508.10251>

[3] *On Evaluating Performance of LLM Inference Serving Systems* (2025).
arXiv:2507.09019. <https://arxiv.org/abs/2507.09019>

[4] Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C. & Sutskever, I.
(2023). *Robust Speech Recognition via Large-Scale Weak Supervision* (Whisper).
OpenAI. <https://cdn.openai.com/papers/whisper.pdf>

[5] Pratap, V. et al. (2024). *Scaling Speech Technology to 1,000+ Languages*
(MMS). *Journal of Machine Learning Research*, 25.
<https://jmlr.org/papers/volume25/23-1318/23-1318.pdf>

[6] Maniati, G. et al. (2022). *SOMOS: The Samsung Open MOS Dataset for the
Evaluation of Neural Text-to-Speech Synthesis*. arXiv:2204.03040.
<https://arxiv.org/abs/2204.03040>

[7] Tan, X. et al. (2022). *NaturalSpeech: End-to-End Text to Speech Synthesis
with Human-Level Quality*. arXiv:2205.04421. <https://arxiv.org/abs/2205.04421>

[8] *Benchmarking the Responsiveness of Open-Source Text-to-Speech Systems*
(2025). *Computers* (MDPI), 14(10), 406. <https://www.mdpi.com/2073-431X/14/10/406>

[9] LiveKit; AssemblyAI; Retell AI (2025–2026). *Voice Agent Architecture: STT,
LLM y TTS Pipelines* (umbrales de latencia conversacional 300–700 ms).
<https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained>

[10] Hugging Face (2026). *Best Open-Source / Open-Weight LLM Models to Run
Locally*. <https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally>

\newpage

# Anexos

- **Código del banco de pruebas:** `benchmarks/`, `common/`, `analysis/`,
  `tools/`.
- **Datos crudos:** `results/*.csv` y `results/*.jsonl`.
- **Tablas y figuras generadas:** `report/tablas_generadas.md`, `report/figures/`.
- **Diagramas del pipeline:** `report/pipeline_diagram.md`.
- **Reproducibilidad:** `README.md`, `Dockerfile`, `docker-compose.yml`.

> _Recordatorio de calidad (rúbrica): revise la ortografía antes de exportar
> (penalización de 0.25 pts por falta) y verifique que ninguna credencial ni
> archivo `.env` se haya subido al repositorio._
