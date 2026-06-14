"""
benchmarks/stt_benchmark.py
===========================
Banco de pruebas para motores de Reconocimiento de Voz (STT).

Catalogo BALANCEADO (config.STT_ENGINES):
  - Nube alta gama   : Deepgram (nova-2), AssemblyAI (best)
  - Nube bajo costo  : Groq Whisper large-v3 (OpenAI-compatible)
  - Local offline    : faster-whisper, openai-whisper, whisper.cpp, Vosk, wav2vec2

Para cada motor transcribe un audio de referencia en espanol y mide latencia
total, RTF (procesamiento/duracion) y WER contra una transcripcion humana.

Los motores en la nube se ACTIVAN solo si su API key esta en .env; los locales
importan sus dependencias de forma perezosa y se omiten si no estan instaladas.

Audio de prueba (16 kHz mono WAV):
    ffmpeg -i tu_audio.mp3 -ar 16000 -ac 1 data/audio/muestra_es.wav

Uso:
    python -m benchmarks.stt_benchmark
    python -m benchmarks.stt_benchmark --engines Deepgram-nova-2 vosk-es-small
    python -m benchmarks.stt_benchmark --only-local
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import wave
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from common.metrics import real_time_factor, word_error_rate
from common.persistence import append_row, dump_jsonl, make_row
from common.timer import LatencySample, measure

RESULTS_CSV = config.RESULTS_DIR / "stt_results.csv"
RESULTS_JSONL = config.RESULTS_DIR / "stt_raw.jsonl"


def audio_duration_s(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 0.0


# --------------------------------------------------------------------------
#  Adaptadores locales (offline). Firma uniforme: (audio, spec) -> texto.
# --------------------------------------------------------------------------
def stt_faster_whisper(audio: Path, spec: dict) -> str:
    from faster_whisper import WhisperModel
    # CPU por defecto (evita depender de cuBLAS/CUDA). Define FW_DEVICE=cuda en
    # .env si tienes una GPU NVIDIA con las librerias instaladas.
    import os as _os
    device = _os.getenv("FW_DEVICE", "cpu")
    compute = "float16" if device == "cuda" else "int8"
    model = WhisperModel(spec["model"], device=device, compute_type=compute)
    segments, _ = model.transcribe(str(audio), language="es")
    return " ".join(seg.text.strip() for seg in segments)


def stt_openai_whisper(audio: Path, spec: dict) -> str:
    import whisper
    model = whisper.load_model(spec["model"])
    return model.transcribe(str(audio), language="es", fp16=False)["text"]


def stt_whisper_cpp(audio: Path, spec: dict) -> str:
    if not config.WHISPER_CPP_BIN or not config.WHISPER_CPP_MODEL:
        raise RuntimeError("Define WHISPER_CPP_BIN y WHISPER_CPP_MODEL en .env")
    out = subprocess.run(
        [config.WHISPER_CPP_BIN, "-m", config.WHISPER_CPP_MODEL, "-f", str(audio), "-l", "es", "-nt"],
        capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[:200])
    return out.stdout.strip()


def stt_vosk(audio: Path, spec: dict) -> str:
    import json as _json

    from vosk import KaldiRecognizer, Model
    mp = spec["model"]
    if not mp or not Path(mp).exists():
        raise RuntimeError(f"Modelo Vosk no encontrado en '{mp}' (ver .env)")
    model = Model(mp)
    with wave.open(str(audio), "rb") as wf:
        rec = KaldiRecognizer(model, wf.getframerate()); rec.SetWords(True)
        words = []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                words.append(_json.loads(rec.Result()).get("text", ""))
        words.append(_json.loads(rec.FinalResult()).get("text", ""))
    return " ".join(w for w in words if w)


def stt_wav2vec2(audio: Path, spec: dict) -> str:
    import librosa
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    processor = Wav2Vec2Processor.from_pretrained(spec["model"])
    model = Wav2Vec2ForCTC.from_pretrained(spec["model"])
    speech, _ = librosa.load(str(audio), sr=16000)
    inputs = processor(speech, sampling_rate=16000, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    return processor.batch_decode(torch.argmax(logits, dim=-1))[0]


# --------------------------------------------------------------------------
#  Adaptadores en la nube (REST). Se activan solo con API key en .env.
# --------------------------------------------------------------------------
def stt_deepgram(audio: Path, spec: dict) -> str:
    url = f"https://api.deepgram.com/v1/listen?model={spec['model']}&language=es&smart_format=true"
    headers = {"Authorization": f"Token {config.get_key(spec)}", "Content-Type": "audio/wav",
               "User-Agent": config.HTTP_USER_AGENT}
    r = requests.post(url, headers=headers, data=audio.read_bytes(), timeout=300)
    r.raise_for_status()
    return r.json()["results"]["channels"][0]["alternatives"][0]["transcript"]


def stt_openai_compat(audio: Path, spec: dict) -> str:
    """Endpoint /audio/transcriptions compatible con OpenAI (Groq, OpenAI)."""
    url = f"{spec['base_url']}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {config.get_key(spec)}", "User-Agent": config.HTTP_USER_AGENT}
    with audio.open("rb") as f:
        files = {"file": (audio.name, f, "audio/wav")}
        data = {"model": spec["model"], "language": "es", "response_format": "json"}
        r = requests.post(url, headers=headers, files=files, data=data, timeout=300)
    r.raise_for_status()
    return r.json().get("text", "")


def stt_assemblyai(audio: Path, spec: dict) -> str:
    base, key = "https://api.assemblyai.com/v2", config.get_key(spec)
    headers = {"authorization": key, "User-Agent": config.HTTP_USER_AGENT}
    up = requests.post(f"{base}/upload", headers=headers, data=audio.read_bytes(), timeout=300)
    up.raise_for_status()
    tr = requests.post(f"{base}/transcript", headers=headers,
                       json={"audio_url": up.json()["upload_url"], "language_code": "es"}, timeout=60)
    tr.raise_for_status()
    tid = tr.json()["id"]
    while True:  # polling hasta completar
        st = requests.get(f"{base}/transcript/{tid}", headers=headers, timeout=60).json()
        if st["status"] == "completed":
            return st["text"]
        if st["status"] == "error":
            raise RuntimeError(st.get("error", "AssemblyAI error"))
        time.sleep(2)


DISPATCH = {
    "faster_whisper": stt_faster_whisper,
    "openai_whisper": stt_openai_whisper,
    "whisper_cpp": stt_whisper_cpp,
    "vosk": stt_vosk,
    "wav2vec2": stt_wav2vec2,
    "deepgram": stt_deepgram,
    "openai_compat_stt": stt_openai_compat,
    "assemblyai": stt_assemblyai,
}


def benchmark_engine(label: str, spec: dict, audio: Path, reference: str,
                     duration: float, n_runs: int) -> None:
    if not config.has_key(spec):
        print(f"  [SKIP] {label}: falta {spec.get('key_env')} en .env.")
        return
    fn = DISPATCH.get(spec["engine"])
    if fn is None:
        print(f"  [SKIP] motor desconocido: {spec['engine']}")
        return

    runs_here = config.CLOUD_N_RUNS if spec.get("kind") == "cloud" else n_runs
    print(f"\n>>> STT: {label}  [{spec['tier']}]")
    total_runs = runs_here + (1 if config.DISCARD_WARMUP else 0)
    for run in range(1, total_runs + 1):
        warmup = config.DISCARD_WARMUP and run == 1
        sample, text = LatencySample(), ""
        try:
            with measure() as elapsed:
                text = fn(audio, spec)
            sample.total_s = elapsed[0]
            wer = word_error_rate(reference, text)
            rtf = real_time_factor(sample.total_s, duration)
            sample.extra = {"wer": round(wer, 4), "rtf": round(rtf, 3)}
        except Exception as e:
            sample.ok = False; sample.error = str(e)
            print(f"    [ERROR] {label}: {str(e)[:80]}")
            append_row(RESULTS_CSV, make_row("STT", label, "muestra_es", run, warmup, sample,
                                             notes=f"tier={spec['tier']}"))
            return
        tag = "calentamiento" if warmup else f"corrida {run - (1 if config.DISCARD_WARMUP else 0)}"
        print(f"    [{tag:14s}] total={sample.total_s:6.2f}s  RTF={sample.extra['rtf']:.2f}  WER={sample.extra['wer']*100:5.1f}%")
        append_row(RESULTS_CSV, make_row(
            "STT", label, "muestra_es", run, warmup, sample,
            metric_name="wer", metric_value=sample.extra["wer"],
            notes=f"tier={spec['tier']}; rtf={sample.extra['rtf']}"))
        dump_jsonl(RESULTS_JSONL, {
            "service": label, "tier": spec["tier"], "run": run, "warmup": warmup,
            "total_s": sample.total_s, "wer": sample.extra["wer"],
            "rtf": sample.extra["rtf"], "hypothesis": text})
        if spec.get("kind") == "cloud" and config.CLOUD_REQUEST_DELAY:
            time.sleep(config.CLOUD_REQUEST_DELAY)


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark de STT (nube + local).")
    p.add_argument("--engines", nargs="*", default=None)
    p.add_argument("--only-local", action="store_true")
    p.add_argument("--runs", type=int, default=config.N_RUNS)
    args = p.parse_args()

    if not config.STT_AUDIO_FILE.exists():
        print(f"[ERROR] Falta el audio de prueba: {config.STT_AUDIO_FILE}")
        print("  Genera uno (16 kHz mono) acorde a data/reference_transcript.txt:")
        print("  ffmpeg -i tu_audio.mp3 -ar 16000 -ac 1 data/audio/muestra_es.wav")
        return

    reference = config.STT_REFERENCE_FILE.read_text(encoding="utf-8").strip()
    duration = audio_duration_s(config.STT_AUDIO_FILE)
    print(f"Audio de prueba: {config.STT_AUDIO_FILE.name} ({duration:.1f}s)")

    selected = dict(config.STT_ENGINES)
    if args.engines:
        selected = {k: v for k, v in selected.items() if k in args.engines}
    if args.only_local:
        selected = {k: v for k, v in selected.items() if v["kind"] == "local"}

    for label, spec in selected.items():
        benchmark_engine(label, spec, config.STT_AUDIO_FILE, reference, duration, args.runs)

    print(f"\nListo. Resultados en: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
