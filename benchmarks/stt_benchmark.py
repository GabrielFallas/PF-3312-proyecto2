"""
benchmarks/stt_benchmark.py
===========================
Banco de pruebas para motores de Reconocimiento de Voz (STT) locales.

Para cada motor transcribe un audio de referencia en espanol y mide:
  - Latencia total de procesamiento (s) y RTF (factor de tiempo real).
  - Word Error Rate (WER) contra una transcripcion de referencia humana.

Motores soportados (todos offline / codigo abierto):
  - faster-whisper  (CTranslate2)        engine="faster_whisper"
  - openai-whisper  (implementacion ref) engine="openai_whisper"
  - whisper.cpp     (binario C++)        engine="whisper_cpp"
  - Vosk            (Kaldi, ligero)      engine="vosk"
  - wav2vec2        (HuggingFace)        engine="wav2vec2"

Las dependencias se importan de forma perezosa: si un motor no esta
instalado, se omite con un aviso en lugar de abortar todo el benchmark.

Preparacion del audio de prueba (16 kHz, mono, WAV):
    ffmpeg -i tu_audio.mp3 -ar 16000 -ac 1 data/audio/muestra_es.wav

Uso:
    python -m benchmarks.stt_benchmark
    python -m benchmarks.stt_benchmark --engines faster-whisper-base vosk-es-small
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from common.metrics import real_time_factor, word_error_rate
from common.persistence import append_row, dump_jsonl, make_row
from common.timer import LatencySample, measure

RESULTS_CSV = config.RESULTS_DIR / "stt_results.csv"
RESULTS_JSONL = config.RESULTS_DIR / "stt_raw.jsonl"


def audio_duration_s(path: Path) -> float:
    """Duracion del WAV en segundos (lectura de cabecera, sin dependencias)."""
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 0.0


# --------------------------------------------------------------------------
#  Adaptadores por motor. Cada uno devuelve el texto transcrito (str).
#  Importes perezosos dentro de cada funcion para no exigir todas las libs.
# --------------------------------------------------------------------------
def transcribe_faster_whisper(audio: Path, model_size: str) -> str:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="auto", compute_type="int8")
    segments, _ = model.transcribe(str(audio), language="es")
    return " ".join(seg.text.strip() for seg in segments)


def transcribe_openai_whisper(audio: Path, model_size: str) -> str:
    import whisper
    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio), language="es", fp16=False)
    return result["text"]


def transcribe_whisper_cpp(audio: Path, _model_size: str) -> str:
    binary = config.WHISPER_CPP_BIN
    model = config.WHISPER_CPP_MODEL
    if not binary or not model:
        raise RuntimeError("Define WHISPER_CPP_BIN y WHISPER_CPP_MODEL en .env")
    out = subprocess.run(
        [binary, "-m", model, "-f", str(audio), "-l", "es", "-nt"],
        capture_output=True, text=True, timeout=600,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr[:200])
    return out.stdout.strip()


def transcribe_vosk(audio: Path, model_path: str) -> str:
    import json as _json

    from vosk import KaldiRecognizer, Model
    if not model_path or not Path(model_path).exists():
        raise RuntimeError(f"Modelo Vosk no encontrado en '{model_path}' (ver .env)")
    model = Model(model_path)
    with wave.open(str(audio), "rb") as wf:
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)
        words: list[str] = []
        while True:
            chunk = wf.readframes(4000)
            if not chunk:
                break
            if rec.AcceptWaveform(chunk):
                words.append(_json.loads(rec.Result()).get("text", ""))
        words.append(_json.loads(rec.FinalResult()).get("text", ""))
    return " ".join(w for w in words if w)


def transcribe_wav2vec2(audio: Path, model_name: str) -> str:
    import librosa
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    processor = Wav2Vec2Processor.from_pretrained(model_name)
    model = Wav2Vec2ForCTC.from_pretrained(model_name)
    speech, _ = librosa.load(str(audio), sr=16000)
    inputs = processor(speech, sampling_rate=16000, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    pred_ids = torch.argmax(logits, dim=-1)
    return processor.batch_decode(pred_ids)[0]


DISPATCH = {
    "faster_whisper": transcribe_faster_whisper,
    "openai_whisper": transcribe_openai_whisper,
    "whisper_cpp": transcribe_whisper_cpp,
    "vosk": transcribe_vosk,
    "wav2vec2": transcribe_wav2vec2,
}


def benchmark_engine(label: str, spec: dict, audio: Path, reference: str,
                     duration: float, n_runs: int) -> None:
    fn = DISPATCH.get(spec["engine"])
    if fn is None:
        print(f"  [SKIP] motor desconocido: {spec['engine']}")
        return

    print(f"\n>>> Motor STT: {label}")
    total_runs = n_runs + (1 if config.DISCARD_WARMUP else 0)
    for run in range(1, total_runs + 1):
        warmup = config.DISCARD_WARMUP and run == 1
        sample = LatencySample()
        text = ""
        try:
            with measure() as elapsed:
                text = fn(audio, spec["model"])
            sample.total_s = elapsed[0]
            wer = word_error_rate(reference, text)
            rtf = real_time_factor(sample.total_s, duration)
            sample.extra = {"wer": round(wer, 4), "rtf": round(rtf, 3)}
        except Exception as e:
            sample.ok = False
            sample.error = str(e)
            print(f"    [ERROR] {label}: {e}")
            append_row(RESULTS_CSV, make_row("STT", label, "muestra_es", run, warmup, sample))
            return  # si falla la carga del motor, no tiene sentido repetir

        tag = "calentamiento" if warmup else f"corrida {run - (1 if config.DISCARD_WARMUP else 0)}"
        print(f"    [{tag:14s}] total={sample.total_s:6.2f}s  RTF={sample.extra['rtf']:.2f}  WER={sample.extra['wer']*100:5.1f}%")

        append_row(RESULTS_CSV, make_row(
            "STT", label, "muestra_es", run, warmup, sample,
            metric_name="wer", metric_value=sample.extra["wer"],
            notes=f"rtf={sample.extra['rtf']}",
        ))
        dump_jsonl(RESULTS_JSONL, {
            "service": label, "run": run, "warmup": warmup,
            "total_s": sample.total_s, "wer": sample.extra["wer"],
            "rtf": sample.extra["rtf"], "hypothesis": text,
        })


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de STT locales.")
    parser.add_argument("--engines", nargs="*", default=None)
    parser.add_argument("--runs", type=int, default=config.N_RUNS)
    args = parser.parse_args()

    if not config.STT_AUDIO_FILE.exists():
        print(f"[ERROR] Falta el audio de prueba: {config.STT_AUDIO_FILE}")
        print("  Genera uno (16 kHz mono) que corresponda a data/reference_transcript.txt, p.ej.:")
        print("  ffmpeg -i tu_audio.mp3 -ar 16000 -ac 1 data/audio/muestra_es.wav")
        return

    reference = config.STT_REFERENCE_FILE.read_text(encoding="utf-8").strip()
    duration = audio_duration_s(config.STT_AUDIO_FILE)
    print(f"Audio de prueba: {config.STT_AUDIO_FILE.name}  ({duration:.1f}s)")

    selected = config.STT_ENGINES
    if args.engines:
        selected = {k: v for k, v in config.STT_ENGINES.items() if k in args.engines}

    for label, spec in selected.items():
        benchmark_engine(label, spec, config.STT_AUDIO_FILE, reference, duration, args.runs)

    print(f"\nListo. Resultados en: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
