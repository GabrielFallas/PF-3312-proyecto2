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

# Pausa (segundos) entre peticiones a servicios EN LA NUBE para respetar los
# limites de peticiones por minuto de las capas gratuitas (free tier). No afecta
# la medicion de latencia (se aplica DESPUES de cronometrar cada corrida).
CLOUD_REQUEST_DELAY = float(os.getenv("CLOUD_REQUEST_DELAY", "1.5"))

# Tope de tokens de SALIDA para LLMs en la nube. Limita el consumo de cuota
# (los free tier mas restrictivos, como Gemini Pro, se agotan rapido) para poder
# repetir las pruebas sin problemas. Los modelos LOCALES no tienen este limite.
# Sube este valor solo si necesitas respuestas mas largas en la nube.
CLOUD_MAX_OUTPUT_TOKENS = int(os.getenv("CLOUD_MAX_OUTPUT_TOKENS", "256"))

# Corridas para servicios en la nube. Por defecto = N_RUNS (rubrica: >= 5), pero
# se puede bajar para conservar cuota durante pruebas exploratorias.
CLOUD_N_RUNS = int(os.getenv("CLOUD_N_RUNS", str(N_RUNS)))

# --- Endpoint de Ollama (LLMs locales) ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# User-Agent para las peticiones a la nube. Algunos proveedores (p.ej. Groq,
# detras de Cloudflare) bloquean el User-Agent por defecto de las librerias HTTP
# (error 1010). Enviar un UA de navegador evita ese bloqueo.
HTTP_USER_AGENT = os.getenv(
    "HTTP_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) benchmarking-ia/1.0",
)


# ==========================================================================
#  CATALOGO DE LLMs  (balance: nube-alta-gama / nube-bajo-costo / local)
# ==========================================================================
LLM_SERVICES = {
    # --- Nube, ALTA GAMA de pago (Gemini 2.5 Pro: modelo flagship de razonamiento
    #     de Google). Free tier muy restrictivo, por lo que se ejecuta con tope de
    #     tokens y "thinking_budget" minimo para no agotar la cuota (ver
    #     CLOUD_MAX_OUTPUT_TOKENS y CLOUD_N_RUNS). Se incluye para tener el punto
    #     de referencia de gama alta que exige el enunciado. ---
    "Gemini-2.5-Pro": {
        "kind": "cloud", "tier": "nube-alta-gama", "provider": "gemini",
        "model": "gemini-2.5-pro", "key_env": "GEMINI_API_KEY",
        "thinking_budget": 128,  # minimo de razonamiento -> conserva cuota
    },
    # --- Nube, ALTA GAMA accesible (Groq sirve modelos flagship open-weight en su
    #     LPU). gpt-oss-120B (OpenAI, 120B) y Llama 4 Scout son modelos de gama alta
    #     con free tier real: dan el punto de referencia empirico de "alta gama en la
    #     nube" que Gemini 2.5 Pro no permite medir gratis (devuelve HTTP 429). ---
    "Groq-GPT-OSS-120B": {
        "kind": "cloud", "tier": "nube-alta-gama", "provider": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b", "key_env": "GROQ_API_KEY",
    },
    "Groq-Llama-4-Scout": {
        "kind": "cloud", "tier": "nube-alta-gama", "provider": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct", "key_env": "GROQ_API_KEY",
    },
    # --- Nube, alta gama (Gemini 2.5 Flash: modelo moderno de la familia flagship,
    #     con free tier mas generoso). ---
    "Gemini-2.5-Flash": {
        "kind": "cloud", "tier": "nube-alta-gama", "provider": "gemini",
        "model": "gemini-2.5-flash", "key_env": "GEMINI_API_KEY",
    },
    # --- Nube, bajo costo / alta velocidad (Gemini 2.5 Flash-Lite: el mas ligero) ---
    "Gemini-2.5-Flash-Lite": {
        "kind": "cloud", "tier": "nube-bajo-costo", "provider": "gemini",
        "model": "gemini-2.5-flash-lite", "key_env": "GEMINI_API_KEY",
    },
    # --- Nube, bajo costo / alta velocidad (Groq LPU, OpenAI-compatible) ---
    # NOTA: ejecuta `python -m tools.check_services` para elegir un modelo vigente.
    # Modelos modernos tipicos en Groq: llama-3.3-70b-versatile, llama-3.1-8b-instant.
    "Groq-Llama-3.3-70B": {
        "kind": "cloud", "tier": "nube-bajo-costo", "provider": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile", "key_env": "GROQ_API_KEY",
    },
    # --- Locales (Ollama, offline). Verifica con `ollama list`/preflight. ---
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
    # --- Nube, alta gama (ElevenLabs free tier; modelo multilingue de calidad) ---
    "ElevenLabs-multilingual-v2": {
        "kind": "cloud", "tier": "nube-alta-gama", "engine": "elevenlabs",
        "model": "eleven_multilingual_v2",
        "voice": os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"),
        "key_env": "ELEVENLABS_API_KEY",
    },
    # --- Nube, bajo costo / alta velocidad (ElevenLabs Flash: moderno, baja latencia) ---
    "ElevenLabs-flash-v2.5": {
        "kind": "cloud", "tier": "nube-bajo-costo", "engine": "elevenlabs",
        "model": "eleven_flash_v2_5",
        "voice": os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"),
        "key_env": "ELEVENLABS_API_KEY",
    },
    # --- Nube, bajo costo / alta velocidad (Deepgram Aura; usa el credito Deepgram) ---
    # NOTA: Aura prioriza ingles; valido como punto de comparacion de latencia.
    "Deepgram-Aura-2": {
        "kind": "cloud", "tier": "nube-bajo-costo", "engine": "deepgram_tts",
        "model": "aura-2-agustina-es", "key_env": "DEEPGRAM_API_KEY",
    },
    # --- Locales (offline) ---
    "piper-es-ES-davefx": {"kind": "local", "tier": "local", "engine": "piper", "voice": os.getenv("PIPER_VOICE", "")},
    "piper-es-MX-claude-high": {"kind": "local", "tier": "local", "engine": "piper", "voice": "models/piper/es_MX-claude-high.onnx"},
    "coqui-xtts-v2": {"kind": "local", "tier": "local", "engine": "coqui", "model": "tts_models/multilingual/multi-dataset/xtts_v2"},
    "kokoro": {"kind": "local", "tier": "local", "engine": "kokoro", "voice": "ef_dora"},
    "espeak-ng": {"kind": "local", "tier": "local", "engine": "espeak", "voice": "es"},
    "bark": {"kind": "local", "tier": "local", "engine": "bark", "voice": "v2/es_speaker_0"},
}


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
