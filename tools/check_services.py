"""
tools/check_services.py
=======================
Preflight (chequeo previo) de los servicios en la nube configurados en .env.

Verifica la VALIDEZ de cada API key y LISTA los modelos disponibles usando
endpoints de SOLO LECTURA (listado/cuenta). NO ejecuta generacion de texto ni
sintesis de audio, por lo que NO consume cuota de uso. Ideal para correr antes
del benchmark cuando el plan gratuito es limitado.

No imprime ninguna llave. Lee las variables desde .env (o el entorno).

Uso:
    python -m tools.check_services
    python -m tools.check_services --show-models     # lista modelos detallada
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    """Carga .env de forma minima (sin dependencias) si las vars no estan ya."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def http_get(url: str, headers: dict, timeout: int = 20):
    # UA de navegador: algunos proveedores (Groq/Cloudflare) bloquean el UA por
    # defecto de urllib (error 1010).
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) benchmarking-ia/1.0"}
    h.update(headers)
    req = urllib.request.Request(url, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def ok(msg: str) -> None:
    print(f"  [ OK ] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def skip(msg: str) -> None:
    print(f"  [skip] {msg}")


def check_groq(show: bool) -> None:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return skip("Groq: sin GROQ_API_KEY")
    try:
        _, data = http_get("https://api.groq.com/openai/v1/models",
                            {"Authorization": f"Bearer {key}"})
        models = sorted(m["id"] for m in data.get("data", []))
        ok(f"Groq: key valida. {len(models)} modelos disponibles.")
        # Resalta modelos de chat modernos (excluye whisper/tts/guard).
        chat = [m for m in models if not any(x in m for x in ("whisper", "tts", "guard", "embed"))]
        print("        Chat/LLM:", ", ".join(chat) if show else ", ".join(chat[:8]) + (" ..." if len(chat) > 8 else ""))
        stt = [m for m in models if "whisper" in m]
        if stt:
            print("        STT:", ", ".join(stt))
    except urllib.error.HTTPError as e:
        fail(f"Groq: HTTP {e.code} (key invalida o sin acceso)")
    except Exception as e:
        fail(f"Groq: {e}")


def check_gemini(show: bool) -> None:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return skip("Gemini: sin GEMINI_API_KEY")
    try:
        _, data = http_get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", {})
        names = [m["name"].replace("models/", "") for m in data.get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        ok(f"Gemini: key valida. {len(names)} modelos con generateContent.")
        modern = [n for n in names if n.startswith(("gemini-2", "gemini-1.5"))]
        print("        LLM:", ", ".join(modern) if show else ", ".join(modern[:8]) + (" ..." if len(modern) > 8 else ""))
    except urllib.error.HTTPError as e:
        fail(f"Gemini: HTTP {e.code} (key invalida o sin acceso)")
    except Exception as e:
        fail(f"Gemini: {e}")


def check_deepgram(show: bool) -> None:
    key = os.getenv("DEEPGRAM_API_KEY", "")
    if not key:
        return skip("Deepgram: sin DEEPGRAM_API_KEY")
    try:
        _, data = http_get("https://api.deepgram.com/v1/projects",
                           {"Authorization": f"Token {key}"})
        n = len(data.get("projects", []))
        ok(f"Deepgram: key valida. {n} proyecto(s) accesible(s).")
    except urllib.error.HTTPError as e:
        fail(f"Deepgram: HTTP {e.code} (key invalida)")
    except Exception as e:
        fail(f"Deepgram: {e}")


def check_assemblyai(show: bool) -> None:
    key = os.getenv("ASSEMBLYAI_API_KEY", "")
    if not key:
        return skip("AssemblyAI: sin ASSEMBLYAI_API_KEY")
    try:
        # Listar transcripciones (limit=1) valida la key sin crear nada.
        _, _data = http_get("https://api.assemblyai.com/v2/transcript?limit=1",
                            {"authorization": key})
        ok("AssemblyAI: key valida.")
    except urllib.error.HTTPError as e:
        fail(f"AssemblyAI: HTTP {e.code} (key invalida)")
    except Exception as e:
        fail(f"AssemblyAI: {e}")


def check_elevenlabs(show: bool) -> None:
    key = os.getenv("ELEVENLABS_API_KEY", "")
    if not key:
        return skip("ElevenLabs: sin ELEVENLABS_API_KEY")
    try:
        _, sub = http_get("https://api.elevenlabs.io/v1/user/subscription",
                          {"xi-api-key": key})
        used = sub.get("character_count", 0)
        limit = sub.get("character_limit", 0)
        ok(f"ElevenLabs: key valida. Uso: {used}/{limit} caracteres.")
        _, models = http_get("https://api.elevenlabs.io/v1/models", {"xi-api-key": key})
        ids = [m["model_id"] for m in models]
        print("        Modelos:", ", ".join(ids) if show else ", ".join(ids[:6]))
    except urllib.error.HTTPError as e:
        fail(f"ElevenLabs: HTTP {e.code} (key invalida)")
    except Exception as e:
        fail(f"ElevenLabs: {e}")


def check_ollama(show: bool) -> None:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        _, data = http_get(f"{host}/api/tags", {})
        models = sorted(m["name"] for m in data.get("models", []))
        ok(f"Ollama: en linea. {len(models)} modelo(s) descargado(s).")
        print("        Local:", ", ".join(models) if models else "(ninguno; usa 'ollama pull')")
    except Exception:
        skip(f"Ollama: no responde en {host} (levantalo con 'ollama serve' o Docker)")


def main() -> None:
    p = argparse.ArgumentParser(description="Preflight de servicios (no consume cuota).")
    p.add_argument("--show-models", action="store_true", help="Lista completa de modelos.")
    args = p.parse_args()
    load_env()

    print("\n=== LLM ===")
    check_gemini(args.show_models)
    check_groq(args.show_models)
    check_ollama(args.show_models)

    print("\n=== STT ===")
    check_deepgram(args.show_models)
    check_assemblyai(args.show_models)
    # Groq Whisper se valida con el check de Groq de arriba.

    print("\n=== TTS ===")
    check_elevenlabs(args.show_models)
    # Deepgram Aura (TTS) usa la misma key de Deepgram validada arriba.

    print("\nPreflight completado. Solo se usaron endpoints de lectura (sin generar).")


if __name__ == "__main__":
    main()
