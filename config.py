"""
config.py
=========
Configuracion central del banco de pruebas (Proyecto 2 - PF-3312).

Carga parametros desde el archivo .env (ver .env.example) y define el
catalogo de servicios a evaluar en cada categoria. Todos los servicios
son de codigo abierto y de ejecucion local/offline.

Centralizar la configuracion aqui hace que los scripts de benchmarking
sean reproducibles: basta editar este archivo (o el .env) para cambiar
modelos, numero de corridas o rutas sin tocar la logica de medicion.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carga .env si existe (no falla si no esta presente).
load_dotenv()

# --- Rutas base del proyecto ---
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
RESULTS_DIR = ROOT / os.getenv("RESULTS_DIR", "results")
MODELS_DIR = ROOT / "models"
TTS_OUTPUT_DIR = ROOT / "tts_output"

for _d in (RESULTS_DIR, AUDIO_DIR, MODELS_DIR, TTS_OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Parametros globales de medicion ---
# La rubrica exige promediar AL MENOS 5 ejecuciones consecutivas.
N_RUNS = int(os.getenv("N_RUNS", "5"))

# Descartar la primera corrida (calentamiento de cache/modelo) del promedio.
DISCARD_WARMUP = True

# --- Ollama (LLMs locales) ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Catalogo de LLMs (etiqueta -> nombre del modelo en Ollama).
# Mezcla de arquitecturas y tamanos para un benchmark representativo.
LLM_MODELS = {
    "Llama-3.1-8B": "llama3.1:8b",
    "Mistral-7B": "mistral:7b",
    "Phi-3.5": "phi3.5",
    "Gemma-2-9B": "gemma2:9b",
    "Qwen-2.5-7B": "qwen2.5:7b",
}

# --- STT (Speech-to-Text) locales ---
# 'engine' indica el modulo/backend que implementa cada motor.
STT_ENGINES = {
    "faster-whisper-base": {"engine": "faster_whisper", "model": "base"},
    "openai-whisper-base": {"engine": "openai_whisper", "model": "base"},
    "whisper.cpp-base": {"engine": "whisper_cpp", "model": "base"},
    "vosk-es-small": {"engine": "vosk", "model": os.getenv("VOSK_MODEL_PATH", "")},
    "wav2vec2-es": {"engine": "wav2vec2", "model": "facebook/wav2vec2-large-xlsr-53-spanish"},
}

# --- TTS (Text-to-Speech) locales ---
TTS_ENGINES = {
    "piper": {"engine": "piper", "voice": os.getenv("PIPER_VOICE", "")},
    "coqui-xtts-v2": {"engine": "coqui", "model": "tts_models/multilingual/multi-dataset/xtts_v2"},
    "kokoro": {"engine": "kokoro", "voice": "ef_dora"},
    "espeak-ng": {"engine": "espeak", "voice": "es"},
    "bark": {"engine": "bark", "voice": "v2/es_speaker_0"},
}

# --- Rutas de binarios/modelos opcionales (desde .env) ---
WHISPER_CPP_BIN = os.getenv("WHISPER_CPP_BIN", "")
WHISPER_CPP_MODEL = os.getenv("WHISPER_CPP_MODEL", "")
VOSK_SAMPLE_RATE = int(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# --- Archivos de prueba controlados ---
LLM_PROMPTS_FILE = DATA_DIR / "prompts_llm.json"
STT_AUDIO_FILE = AUDIO_DIR / "muestra_es.wav"          # audio de referencia (16 kHz mono)
STT_REFERENCE_FILE = DATA_DIR / "reference_transcript.txt"
TTS_TEXT_FILE = DATA_DIR / "tts_text_es.txt"
