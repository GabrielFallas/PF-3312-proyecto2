# Tablas y figuras generadas automaticamente

_Generado por `analysis/build_report_data.py` a partir de los CSV crudos. Excluye corridas de calentamiento._

### LLM — latencia y velocidad

| Servicio | Latencia total (s) | TTFT (s) | Tokens/seg |
|---|---|---|---|
| Gemini-2.5-Flash | 1.888 ± 0.232 | 1.791 ± 0.234 | 20.329 ± 16.200 |
| Gemini-2.5-Flash-Lite | 0.949 ± 0.175 | 0.674 ± 0.113 | 99.640 ± 55.802 |
| Gemma-2-9B-local | 1.018 ± 0.520 | 0.103 ± 0.012 | 115.140 ± 1.557 |
| Groq-Llama-3.3-70B | 0.732 ± 0.219 | 0.396 ± 0.036 | 139.998 ± 72.031 |
| Llama-3.1-8B-local | 0.904 ± 0.432 | 0.105 ± 0.009 | 142.492 ± 2.308 |
| Mistral-7B-local | 0.855 ± 0.506 | 0.034 ± 0.010 | 150.355 ± 5.819 |
| Phi-3.5-local | 0.603 ± 0.299 | 0.031 ± 0.008 | 256.826 ± 3.176 |
| Qwen-2.5-7B-local | 0.624 ± 0.394 | 0.090 ± 0.010 | 155.414 ± 2.286 |

### STT — latencia y precision

| Servicio | Latencia (s) | WER |
|---|---|---|
| AssemblyAI-best | 5.696 ± 0.251 | 0.000 ± 0.000 |
| Deepgram-nova-2 | 1.500 ± 0.232 | 0.000 ± 0.000 |
| Groq-Whisper-large-v3 | 2.481 ± 0.421 | 0.000 ± 0.000 |
| faster-whisper-base | 0.906 ± 0.035 | 0.000 ± 0.000 |
| vosk-es-small | 0.956 ± 0.018 | 0.000 ± 0.000 |

### TTS — latencia y eficiencia (RTF)

| Servicio | Latencia sintesis (s) | RTF |
|---|---|---|
| Deepgram-Aura-2 | 6.888 ± 0.341 | 0.490 ± 0.004 |
| ElevenLabs-flash-v2.5 | 1.200 ± 0.044 | 0.092 ± 0.004 |
| ElevenLabs-multilingual-v2 | 2.159 ± 0.084 | 0.168 ± 0.007 |
| piper-es-ES-davefx | 1.755 ± 0.014 | 0.149 ± 0.002 |
| piper-es-MX-claude-high | 1.496 ± 0.021 | 0.112 ± 0.002 |
