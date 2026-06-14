"""
tools/make_test_audio.py
========================
Genera el audio de prueba para el benchmark de STT a partir de la transcripcion
de referencia (data/reference_transcript.txt), usando ElevenLabs en formato
PCM 16 kHz mono, y lo envuelve en un WAV (sin depender de ffmpeg).

Esto crea una entrada CONTROLADA y reproducible: el texto sintetizado coincide
exactamente con la referencia, de modo que el WER mide el error de cada motor
STT sobre el mismo material. Se documenta en el reporte que el audio de prueba
es voz sintetica limpia (util para comparar motores entre si).

Uso:
    python -m tools.make_test_audio
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

SAMPLE_RATE = 16000


def main() -> None:
    voice = config.TTS_ENGINES["ElevenLabs-multilingual-v2"]
    key = config.get_key(voice)
    if not key:
        sys.exit("Falta ELEVENLABS_API_KEY en .env")

    text = config.STT_REFERENCE_FILE.read_text(encoding="utf-8").strip()
    voice_id = voice["voice"]
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
           f"?output_format=pcm_16000")
    headers = {"xi-api-key": key, "Content-Type": "application/json",
               "User-Agent": config.HTTP_USER_AGENT}
    payload = {"text": text, "model_id": "eleven_multilingual_v2"}

    print(f"Sintetizando audio de prueba ({len(text)} caracteres) con ElevenLabs...")
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    pcm = r.content  # PCM crudo: 16-bit LE, mono, 16 kHz

    out = config.STT_AUDIO_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16 bits
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    dur = len(pcm) / 2 / SAMPLE_RATE
    print(f"Audio guardado en {out}  ({dur:.1f}s, 16 kHz mono).")
    print("Referencia:", text[:70], "...")


if __name__ == "__main__":
    main()
