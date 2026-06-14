"""
benchmarks/tts_benchmark.py
===========================
Banco de pruebas para motores de Sintesis de Voz (TTS).

Catalogo BALANCEADO (config.TTS_ENGINES):
  - Nube alta gama   : ElevenLabs (multilingual v2), Azure TTS (es-CR)
  - Nube bajo costo  : OpenAI tts-1
  - Local offline    : Piper, Coqui XTTS v2, Kokoro, eSpeak-NG, Bark

Para cada motor sintetiza un texto en espanol y mide latencia de sintesis,
duracion del audio y RTF. Guarda el audio en tts_output/ para la valoracion
CUALITATIVA de inteligibilidad y naturalidad.

Los motores en la nube se ACTIVAN solo si su API key esta en .env.

Uso:
    python -m benchmarks.tts_benchmark
    python -m benchmarks.tts_benchmark --engines piper OpenAI-tts-1
    python -m benchmarks.tts_benchmark --only-local
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from common.metrics import real_time_factor
from common.persistence import append_row, make_row
from common.timer import LatencySample, measure

RESULTS_CSV = config.RESULTS_DIR / "tts_results.csv"


def audio_duration_s(path: Path) -> float:
    """Duracion en segundos. WAV via modulo `wave`; otros formatos via librosa."""
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        try:
            import librosa
            return float(librosa.get_duration(path=str(path)))
        except Exception:
            return 0.0


# --------------------------------------------------------------------------
#  Adaptadores locales (offline). Firma: (text, out, spec) -> ruta de salida.
# --------------------------------------------------------------------------
def tts_piper(text: str, out: Path, spec: dict) -> Path:
    voice = spec.get("voice")
    if not voice or not Path(voice).exists():
        raise RuntimeError(f"Voz Piper no encontrada en '{voice}' (ver .env)")
    proc = subprocess.run(["piper", "--model", voice, "--output_file", str(out)],
                          input=text, text=True, capture_output=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:200])
    return out


def tts_espeak(text: str, out: Path, spec: dict) -> Path:
    proc = subprocess.run(["espeak-ng", "-v", spec.get("voice", "es"), "-w", str(out), text],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:200])
    return out


def tts_coqui(text: str, out: Path, spec: dict) -> Path:
    from TTS.api import TTS
    tts = TTS(spec["model"])
    speaker_wav = config.AUDIO_DIR / "speaker_ref.wav"
    kwargs = {"text": text, "file_path": str(out), "language": "es"}
    if speaker_wav.exists():
        kwargs["speaker_wav"] = str(speaker_wav)
    tts.tts_to_file(**kwargs)
    return out


def tts_kokoro(text: str, out: Path, spec: dict) -> Path:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    pipeline = KPipeline(lang_code="e")
    chunks = [audio for _, _, audio in pipeline(text, voice=spec.get("voice", "ef_dora"))]
    sf.write(str(out), np.concatenate(chunks), 24000)
    return out


def tts_bark(text: str, out: Path, spec: dict) -> Path:
    import soundfile as sf
    from bark import SAMPLE_RATE, generate_audio, preload_models
    preload_models()
    sf.write(str(out), generate_audio(text, history_prompt=spec.get("voice")), SAMPLE_RATE)
    return out


# --------------------------------------------------------------------------
#  Adaptadores en la nube (REST). Se activan solo con API key en .env.
# --------------------------------------------------------------------------
def tts_elevenlabs(text: str, out: Path, spec: dict) -> Path:
    out = out.with_suffix(".mp3")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{spec['voice']}?output_format=mp3_44100_128"
    headers = {"xi-api-key": config.get_key(spec), "Content-Type": "application/json"}
    payload = {"text": text, "model_id": spec["model"]}
    r = requests.post(url, headers=headers, json=payload, timeout=300)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


def tts_openai(text: str, out: Path, spec: dict) -> Path:
    url = f"{spec['base_url']}/audio/speech"
    headers = {"Authorization": f"Bearer {config.get_key(spec)}", "Content-Type": "application/json"}
    payload = {"model": spec["model"], "voice": spec["voice"], "input": text, "response_format": "wav"}
    r = requests.post(url, headers=headers, json=payload, timeout=300)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


def tts_azure(text: str, out: Path, spec: dict) -> Path:
    region = config.AZURE_SPEECH_REGION
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": config.get_key(spec),
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
    }
    voice = spec.get("voice", "es-CR-JuanNeural")
    ssml = (f"<speak version='1.0' xml:lang='es-CR'><voice xml:lang='es-CR' "
            f"name='{voice}'>{text}</voice></speak>")
    r = requests.post(url, headers=headers, data=ssml.encode("utf-8"), timeout=300)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


DISPATCH = {
    "piper": tts_piper, "espeak": tts_espeak, "coqui": tts_coqui,
    "kokoro": tts_kokoro, "bark": tts_bark,
    "elevenlabs": tts_elevenlabs, "openai_tts": tts_openai, "azure": tts_azure,
}


def benchmark_engine(label: str, spec: dict, text: str, n_runs: int) -> None:
    if not config.has_key(spec):
        print(f"  [SKIP] {label}: falta {spec.get('key_env')} en .env.")
        return
    fn = DISPATCH.get(spec["engine"])
    if fn is None:
        print(f"  [SKIP] motor desconocido: {spec['engine']}")
        return

    print(f"\n>>> TTS: {label}  [{spec['tier']}]")
    total_runs = n_runs + (1 if config.DISCARD_WARMUP else 0)
    for run in range(1, total_runs + 1):
        warmup = config.DISCARD_WARMUP and run == 1
        out_wav = config.TTS_OUTPUT_DIR / f"{label}_run{run}.wav"
        sample = LatencySample()
        try:
            with measure() as elapsed:
                produced = fn(text, out_wav, spec)
            sample.total_s = elapsed[0]
            dur = audio_duration_s(produced)
            sample.extra = {"audio_s": round(dur, 3), "rtf": round(real_time_factor(sample.total_s, dur), 3)}
        except Exception as e:
            sample.ok = False; sample.error = str(e)
            print(f"    [ERROR] {label}: {str(e)[:80]}")
            append_row(RESULTS_CSV, make_row("TTS", label, "tts_text_es", run, warmup, sample,
                                             notes=f"tier={spec['tier']}"))
            return
        tag = "calentamiento" if warmup else f"corrida {run - (1 if config.DISCARD_WARMUP else 0)}"
        print(f"    [{tag:14s}] sintesis={sample.total_s:6.2f}s  audio={sample.extra['audio_s']:.2f}s  RTF={sample.extra['rtf']:.2f}")
        append_row(RESULTS_CSV, make_row(
            "TTS", label, "tts_text_es", run, warmup, sample,
            metric_name="rtf", metric_value=sample.extra["rtf"],
            notes=f"tier={spec['tier']}; audio_s={sample.extra['audio_s']}"))


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark de TTS (nube + local).")
    p.add_argument("--engines", nargs="*", default=None)
    p.add_argument("--only-local", action="store_true")
    p.add_argument("--runs", type=int, default=config.N_RUNS)
    args = p.parse_args()

    text = config.TTS_TEXT_FILE.read_text(encoding="utf-8").strip()
    print(f"Texto de prueba ({len(text)} caracteres): {text[:60]}...")

    selected = dict(config.TTS_ENGINES)
    if args.engines:
        selected = {k: v for k, v in selected.items() if k in args.engines}
    if args.only_local:
        selected = {k: v for k, v in selected.items() if v["kind"] == "local"}

    for label, spec in selected.items():
        benchmark_engine(label, spec, text, args.runs)

    print(f"\nListo. Resultados en: {RESULTS_CSV}")
    print(f"Audios para evaluacion cualitativa en: {config.TTS_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
