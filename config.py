"""
config.py
=========
Configuracion central del banco de pruebas (Proyecto 2 - PF-3312).

Carga parametros desde .env (ver .env.example) y define el catalogo de
servicios a evaluar en cada categoria. La muestra incluye, por exigencia del
enunciado, un BALANCE REPRESENTATIVO de tres tipos:

  - "nube-alta-gama"  : servicios comerciales de alta gama en la nube.
  - "nube-bajo-costo" : APIs comerciales de bajo costo o alta velocidad.
  - "local"           : modelos de codigo abierto, ejecucion offline.

Para evitar costos, los servicios en la nube se consumen mediante sus CAPAS
GRATUITAS (free tier). Cada servicio en la nube se ACTIVA solo si su variable
de entorno con la API key esta presente; de lo contrario se omite con un aviso.
Nunca se exponen llaves: se leen de .env (ignorado por git).

Campos por servicio:
  kind      : "cloud" | "local"
  tier      : "nube-alta-gama" | "nube-bajo-costo" | "local"
  provider  : adaptador que lo implementa (ollama, openai_compat, gemini, ...)
  model     : identificador del modelo en su proveedor
  base_url  : (cloud OpenAI-compatibles) endpoint base
  key_env   : (cloud) nombre de la variable de entorno con la API key
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

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
N_RUNS = int(os.getenv("N_RUNS", "5"))      # rubrica: >= 5 corridas limpias
DISCARD_WARMUP = True                       # descartar la 1a corrida (calentamiento)

# --- Endpoint de Ollama (LLMs locales) ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


# ==========================================================================
#  CATALOGO DE LLMs  (balance: nube-alta-gama / nube-bajo-costo / local)
# ==========================================================================
LLM_SERVICES = {
    # --- Nube, alta gama (free tier de Google AI Studio) ---
    "Gemini-1.5-Pro": {
        "kind": "cloud", "tier": "nube-alta-gama", "provider": "gemini",
        "model": "gemini-1.5-pro", "key_env": "GEMINI_API_KEY",
    },
    # --- Nube, alta gama (OpenAI; opcional, requiere saldo) ---
    "GPT-4o": {
        "kind": "cloud", "tier": "nube-alta-gama", "provider": "openai_compat",
        "base_url": "https://api.openai.com/v1", "model": "gpt-4o",
        "key_env": "OPENAI_API_KEY",
    },
    # --- Nube, bajo costo / alta velocidad (Groq free tier, OpenAI-compatible) ---
    "Groq-Llama-3.3-70B": {
        "kind": "cloud", "tier": "nube-bajo-costo", "provider": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile", "key_env": "GROQ_API_KEY",
    },
    # --- Locales (Ollama, offline) ---
    "Llama-3.1-8B-local": {"kind": "local", "tier": "local", "provider": "ollama", "model": "llama3.1:8b"},
    "Mistral-7B-local": {"kind": "local", "tier": "local", "provider": "ollama", "model": "mistral:7b"},
    "Phi-3.5-local": {"kind": "local", "tier": "local", "provider": "ollama", "model": "phi3.5"},
    "Gemma-2-9B-local": {"kind": "local", "tier": "local", "provider": "ollama", "model": "gemma2:9b"},
    "Qwen-2.5-7B-local": {"kind": "local", "tier": "local", "provider": "ollama", "model": "qwen2.5:7b"},
}

# Compatibilidad con scripts/documentacion previos.
LLM_MODELS = {k: v["model"] for k, v in LLM_SERVICES.items() if v["provider"] == "ollama"}


# ==========================================================================
#  CATALOGO DE STT  (balance: nube-alta-gama / nube-bajo-costo / local)
# ==========================================================================
STT_ENGINES = {
    # --- Nube, alta gama (creditos gratuitos) ---
    "Deepgram-nova-2": {
        "kind": "cloud", "tier": "nube-alta-gama", "engine": "deepgram",
        "model": "nova-2", "key_env": "DEEPGRAM_API_KEY",
    },
    "AssemblyAI-best": {
        "kind": "cloud", "tier": "nube-alta-gama", "engine": "assemblyai",
        "model": "best", "key_env": "ASSEMBLYAI_API_KEY",
    },
    # --- Nube, bajo costo / alta velocidad (Groq Whisper, OpenAI-compatible) ---
    "Groq-Whisper-large-v3": {
        "kind": "cloud", "tier": "nube-bajo-costo", "engine": "openai_compat_stt",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "whisper-large-v3", "key_env": "GROQ_API_KEY",
    },
    # --- Locales (offline) ---
    "faster-whisper-base": {"kind": "local", "tier": "local", "engine": "faster_whisper", "model": "base"},
    "openai-whisper-base": {"kind": "local", "tier": "local", "engine": "openai_whisper", "model": "base"},
    "whisper.cpp-base": {"kind": "local", "tier": "local", "engine": "whisper_cpp", "model": "base"},
    "vosk-es-small": {"kind": "local", "tier": "local", "engine": "vosk", "model": os.getenv("VOSK_MODEL_PATH", "")},
    "wav2vec2-es": {"kind": "local", "tier": "local", "engine": "wav2vec2", "model": "facebook/wav2vec2-large-xlsr-53-spanish"},
}


# ==========================================================================
#  CATALOGO DE TTS  (balance: nube-alta-gama / nube-bajo-costo / local)
# ==========================================================================
TTS_ENGINES = {
    # --- Nube, alta gama (free tier) ---
    "ElevenLabs-multilingual-v2": {
        "kind": "cloud", "tier": "nube-alta-gama", "engine": "elevenlabs",
        "model": "eleven_multilingual_v2",
        "voice": os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"),
        "key_env": "ELEVENLABS_API_KEY",
    },
    "Azure-TTS-es": {
        "kind": "cloud", "tier": "nube-alta-gama", "engine": "azure",
        "voice": "es-CR-JuanNeural", "key_env": "AZURE_SPEECH_KEY",
    },
    # --- Nube, bajo costo (OpenAI TTS) ---
    "OpenAI-tts-1": {
        "kind": "cloud", "tier": "nube-bajo-costo", "engine": "openai_tts",
        "base_url": "https://api.openai.com/v1", "model": "tts-1",
        "voice": "alloy", "key_env": "OPENAI_API_KEY",
    },
    # --- Locales (offline) ---
    "piper": {"kind": "local", "tier": "local", "engine": "piper", "voice": os.getenv("PIPER_VOICE", "")},
    "coqui-xtts-v2": {"kind": "local", "tier": "local", "engine": "coqui", "model": "tts_models/multilingual/multi-dataset/xtts_v2"},
    "kokoro": {"kind": "local", "tier": "local", "engine": "kokoro", "voice": "ef_dora"},
    "espeak-ng": {"kind": "local", "tier": "local", "engine": "espeak", "voice": "es"},
    "bark": {"kind": "local", "tier": "local", "engine": "bark", "voice": "v2/es_speaker_0"},
}


# --- Parametros de servicios en la nube ---
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")

# --- Rutas de binarios/modelos locales opcionales (desde .env) ---
WHISPER_CPP_BIN = os.getenv("WHISPER_CPP_BIN", "")
WHISPER_CPP_MODEL = os.getenv("WHISPER_CPP_MODEL", "")
VOSK_SAMPLE_RATE = int(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# --- Archivos de prueba controlados ---
LLM_PROMPTS_FILE = DATA_DIR / "prompts_llm.json"
STT_AUDIO_FILE = AUDIO_DIR / "muestra_es.wav"
STT_REFERENCE_FILE = DATA_DIR / "reference_transcript.txt"
TTS_TEXT_FILE = DATA_DIR / "tts_text_es.txt"


def has_key(service: dict) -> bool:
    """True si el servicio es local, o es cloud y su API key esta en el entorno."""
    if service.get("kind") != "cloud":
        return True
    return bool(os.getenv(service.get("key_env", ""), ""))


def get_key(service: dict) -> str:
    return os.getenv(service.get("key_env", ""), "")
