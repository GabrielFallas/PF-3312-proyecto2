"""
run_all.py
==========
Orquestador del banco de pruebas completo. Ejecuta, en orden, los tres
benchmarks y la consolidacion de resultados. Pensado para correr dentro del
contenedor Docker (ver docker-compose.yml) o en local.

Cada etapa se aisla: si una categoria falla (p.ej. faltan dependencias de
TTS), las demas continuan. Util para entornos donde no todos los motores
estan instalados.

Uso:
    python run_all.py                 # todo, con N_RUNS de config
    python run_all.py --only llm stt  # solo categorias indicadas
    python run_all.py --runs 5
"""
from __future__ import annotations

import argparse
import sys

from benchmarks import llm_benchmark, stt_benchmark, tts_benchmark
from analysis import build_report_data

STAGES = {
    "llm": ("Modelos de Lenguaje (LLM)", llm_benchmark.main),
    "stt": ("Reconocimiento de Voz (STT)", stt_benchmark.main),
    "tts": ("Sintesis de Voz (TTS)", tts_benchmark.main),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta el banco de pruebas completo.")
    parser.add_argument("--only", nargs="*", choices=list(STAGES), default=list(STAGES))
    parser.add_argument("--runs", type=int, default=None)
    args = parser.parse_args()

    # Propaga --runs a los sub-scripts via sys.argv reconstruido por etapa.
    for key in args.only:
        title, fn = STAGES[key]
        print("\n" + "=" * 66)
        print(f"  ETAPA: {title}")
        print("=" * 66)
        sys.argv = [key] + (["--runs", str(args.runs)] if args.runs else [])
        try:
            fn()
        except SystemExit:
            pass
        except Exception as e:  # no abortar todo por una categoria
            print(f"  [FALLO en {key}] {e}")

    print("\n" + "=" * 66)
    print("  CONSOLIDACION DE RESULTADOS")
    print("=" * 66)
    sys.argv = ["build_report_data"]
    try:
        build_report_data.main()
    except Exception as e:
        print(f"  [FALLO en consolidacion] {e}")


if __name__ == "__main__":
    main()
