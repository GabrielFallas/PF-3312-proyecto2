"""
tools/setup_models.py
=====================
Descarga, de forma automatica y reproducible, los modelos LOCALES (offline)
que el banco de pruebas usa pero que NO se versionan en git por su tamano:

  - Vosk (reconocimiento de voz en espanol, modelo small ~40 MB)
  - Piper (dos voces neuronales en espanol: es_ES-davefx y es_MX-claude)

Los coloca en `models/` con las rutas que esperan `config.py` y `.env`. Si un
modelo ya existe, lo omite (idempotente). Tras ejecutarlo, los benchmarks de
STT/TTS locales corren sin ninguna clave de API:

    python -m tools.setup_models
    python -m benchmarks.stt_benchmark --only-local
    python -m benchmarks.tts_benchmark --only-local

Los LLM locales se descargan por separado con Ollama (ver README):
    ollama pull llama3.1:8b mistral:7b phi3.5 gemma2:9b qwen2.5:7b
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

UA = {"User-Agent": config.HTTP_USER_AGENT}

VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
VOSK_DIR = config.MODELS_DIR / "vosk-model-small-es-0.42"

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es"
PIPER_DIR = config.MODELS_DIR / "piper"
PIPER_VOICES = {
    "es_ES-davefx-medium": f"{PIPER_BASE}/es_ES/davefx/medium",
    "es_MX-claude-high": f"{PIPER_BASE}/es_MX/claude/high",
}


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Descargando {url.split('/')[-1]} ...", flush=True)
    with requests.get(url, headers=UA, stream=True, timeout=600) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    print(f"    -> {dest}  ({dest.stat().st_size/1e6:.1f} MB)")


def setup_vosk() -> None:
    print("[Vosk] modelo de espanol (small)")
    if VOSK_DIR.exists():
        print(f"  Ya existe: {VOSK_DIR} (omitido)")
        return
    print(f"  Descargando y descomprimiendo desde {VOSK_URL} ...", flush=True)
    r = requests.get(VOSK_URL, headers=UA, timeout=900)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(config.MODELS_DIR)
    print(f"  -> {VOSK_DIR}")


def setup_piper() -> None:
    print("[Piper] voces neuronales en espanol")
    for name, base in PIPER_VOICES.items():
        onnx = PIPER_DIR / f"{name}.onnx"
        meta = PIPER_DIR / f"{name}.onnx.json"
        if onnx.exists() and meta.exists():
            print(f"  Ya existe: {name} (omitido)")
            continue
        _download(f"{base}/{name}.onnx", onnx)
        _download(f"{base}/{name}.onnx.json", meta)


def main() -> None:
    print(f"Directorio de modelos: {config.MODELS_DIR}\n")
    ok = True
    for step in (setup_vosk, setup_piper):
        try:
            step()
        except Exception as e:  # no abortar todo por un modelo
            ok = False
            print(f"  [ERROR] {step.__name__}: {e}")
        print()
    print("Listo." if ok else "Terminado con errores (revisa los mensajes de arriba).")
    print("Ahora puedes correr:  python -m benchmarks.stt_benchmark --only-local")


if __name__ == "__main__":
    main()
