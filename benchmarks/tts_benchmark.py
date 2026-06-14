"""
benchmarks/tts_benchmark.py
===========================
Banco de pruebas para motores de Sintesis de Voz (TTS) locales.

Para cada motor sintetiza un texto en espanol y mide:
  - Latencia total de sintesis (s).
  - Duracion del audio generado y RTF (procesamiento / duracion).
  - Guarda el WAV resultante en tts_output/ para la valoracion CUALITATIVA
    de inteligibilidad y naturalidad (dimension de calidad del TTS).

Motores soportados (offline / codigo abierto):
  - Piper      (ONNX, muy rapido)     engine="piper"
  - Coqui XTTS v2 (clonacion de voz)  engine="coqui"
  - Kokoro     (ligero, alta calidad) engine="kokoro"
  - eSpeak-NG  (formant, baseline)    engine="espeak"
  - Bark       (generativo, expresivo)engine="bark"

Uso:
    python -m benchmarks.tts_benchmark
    python -m benchmarks.tts_benchmark --engines piper espeak-ng
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from common.metrics import real_time_factor
from common.persistence import append_row, make_row
from common.timer import LatencySample, measure

RESULTS_CSV = config.RESULTS_DIR / "tts_results.csv"


def wav_duration_s(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 0.0


# --------------------------------------------------------------------------
#  Adaptadores por motor. Cada uno sintetiza `text` en `out_wav`.
# --------------------------------------------------------------------------
def synth_piper(text: str, out_wav: Path, spec: dict) -> None:
    voice = spec.get("voice")
    if not voice or not Path(voice).exists():
        raise RuntimeError(f"Voz Piper no encontrada en '{voice}' (ver .env / models/piper)")
    # piper lee el texto por stdin y escribe el WAV indicado.
    proc = subprocess.run(
        ["piper", "--model", voice, "--output_file", str(out_wav)],
        input=text, text=True, capture_output=True, timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:200])


def synth_espeak(text: str, out_wav: Path, spec: dict) -> None:
    # espeak-ng debe estar instalado a nivel de sistema (apt/choco install espeak-ng).
    proc = subprocess.run(
        ["espeak-ng", "-v", spec.get("voice", "es"), "-w", str(out_wav), text],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:200])


def synth_coqui(text: str, out_wav: Path, spec: dict) -> None:
    from TTS.api import TTS
    tts = TTS(spec["model"])
    # XTTS v2 requiere un audio de referencia para la voz; usa uno corto en data/audio.
    speaker_wav = config.AUDIO_DIR / "speaker_ref.wav"
    kwargs = {"text": text, "file_path": str(out_wav), "language": "es"}
    if speaker_wav.exists():
        kwargs["speaker_wav"] = str(speaker_wav)
    tts.tts_to_file(**kwargs)


def synth_kokoro(text: str, out_wav: Path, spec: dict) -> None:
    import soundfile as sf
    from kokoro import KPipeline
    pipeline = KPipeline(lang_code="e")  # 'e' = espanol
    audio_chunks = []
    for _, _, audio in pipeline(text, voice=spec.get("voice", "ef_dora")):
        audio_chunks.append(audio)
    import numpy as np
    sf.write(str(out_wav), np.concatenate(audio_chunks), 24000)


def synth_bark(text: str, out_wav: Path, spec: dict) -> None:
    import soundfile as sf
    from bark import SAMPLE_RATE, generate_audio, preload_models
    preload_models()
    audio = generate_audio(text, history_prompt=spec.get("voice"))
    sf.write(str(out_wav), audio, SAMPLE_RATE)


DISPATCH = {
    "piper": synth_piper,
    "espeak": synth_espeak,
    "coqui": synth_coqui,
    "kokoro": synth_kokoro,
    "bark": synth_bark,
}


def benchmark_engine(label: str, spec: dict, text: str, n_runs: int) -> None:
    fn = DISPATCH.get(spec["engine"])
    if fn is None:
        print(f"  [SKIP] motor desconocido: {spec['engine']}")
        return

    print(f"\n>>> Motor TTS: {label}")
    total_runs = n_runs + (1 if config.DISCARD_WARMUP else 0)
    for run in range(1, total_runs + 1):
        warmup = config.DISCARD_WARMUP and run == 1
        out_wav = config.TTS_OUTPUT_DIR / f"{label}_run{run}.wav"
        sample = LatencySample()
        try:
            with measure() as elapsed:
                fn(text, out_wav, spec)
            sample.total_s = elapsed[0]
            dur = wav_duration_s(out_wav)
            rtf = real_time_factor(sample.total_s, dur)
            sample.extra = {"audio_s": round(dur, 3), "rtf": round(rtf, 3)}
        except Exception as e:
            sample.ok = False
            sample.error = str(e)
            print(f"    [ERROR] {label}: {e}")
            append_row(RESULTS_CSV, make_row("TTS", label, "tts_text_es", run, warmup, sample))
            return

        tag = "calentamiento" if warmup else f"corrida {run - (1 if config.DISCARD_WARMUP else 0)}"
        print(f"    [{tag:14s}] sintesis={sample.total_s:6.2f}s  audio={sample.extra['audio_s']:.2f}s  RTF={sample.extra['rtf']:.2f}")

        append_row(RESULTS_CSV, make_row(
            "TTS", label, "tts_text_es", run, warmup, sample,
            metric_name="rtf", metric_value=sample.extra["rtf"],
            notes=f"audio_s={sample.extra['audio_s']}; wav={out_wav.name}",
        ))


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de TTS locales.")
    parser.add_argument("--engines", nargs="*", default=None)
    parser.add_argument("--runs", type=int, default=config.N_RUNS)
    args = parser.parse_args()

    text = config.TTS_TEXT_FILE.read_text(encoding="utf-8").strip()
    print(f"Texto de prueba ({len(text)} caracteres): {text[:60]}...")

    selected = config.TTS_ENGINES
    if args.engines:
        selected = {k: v for k, v in config.TTS_ENGINES.items() if k in args.engines}

    for label, spec in selected.items():
        benchmark_engine(label, spec, text, args.runs)

    print(f"\nListo. Resultados en: {RESULTS_CSV}")
    print(f"Audios para evaluacion cualitativa en: {config.TTS_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
