"""
benchmarks/llm_benchmark.py
===========================
Banco de pruebas para Modelos de Lenguaje (LLM) locales servidos por Ollama.

Mide, para cada modelo y cada prompt controlado:
  - TTFT  (Time To First Token)  -> latencia percibida en una conversacion.
  - Latencia total de respuesta.
  - Velocidad de generacion (tokens/seg) reportada por Ollama.

Promedia N_RUNS corridas (descartando la de calentamiento) y persiste cada
ejecucion individual en results/llm_results.csv para su analisis posterior.

Requisitos:
  1. Ollama instalado y corriendo (https://ollama.com) o via Docker.
  2. Los modelos de config.LLM_MODELS descargados:  `ollama pull <modelo>`.

Uso:
    python -m benchmarks.llm_benchmark
    python -m benchmarks.llm_benchmark --models Llama-3.1-8B Mistral-7B
    python -m benchmarks.llm_benchmark --runs 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

# Permite ejecutar como script suelto o como modulo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from common.persistence import CSV_FIELDS, append_row, dump_jsonl, make_row
from common.timer import StreamTimer

RESULTS_CSV = config.RESULTS_DIR / "llm_results.csv"
RESULTS_JSONL = config.RESULTS_DIR / "llm_raw.jsonl"


def list_available_models() -> set[str]:
    """Consulta a Ollama que modelos estan descargados localmente."""
    try:
        r = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=10)
        r.raise_for_status()
        return {m["name"] for m in r.json().get("models", [])}
    except requests.RequestException as e:
        print(f"  [ERROR] No se pudo contactar a Ollama en {config.OLLAMA_HOST}: {e}")
        print("          Verifica que el servicio este corriendo: `ollama serve`")
        return set()


def run_single(model_id: str, system: str, prompt: str, max_tokens: int):
    """Ejecuta UNA generacion en streaming y cronometra TTFT + total.

    Devuelve (LatencySample, texto_generado). El stream de Ollama emite un
    JSON por linea; el primer fragmento con 'response' no vacio marca el TTFT
    y el fragmento con 'done': true cierra la medicion y trae las metricas
    nativas (eval_count, eval_duration) para calcular tokens/seg.
    """
    timer = StreamTimer()
    payload = {
        "model": model_id,
        "prompt": prompt,
        "system": system,
        "stream": True,
        "options": {"num_predict": max_tokens, "temperature": 0.0},
    }
    pieces: list[str] = []
    eval_count = 0
    eval_duration_ns = 0

    timer.start()
    try:
        with requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json=payload, stream=True, timeout=300,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("response", "")
                if token:
                    timer.mark_first_token()
                    pieces.append(token)
                if chunk.get("done"):
                    eval_count = chunk.get("eval_count", 0) or 0
                    eval_duration_ns = chunk.get("eval_duration", 0) or 0
    except (requests.RequestException, json.JSONDecodeError) as e:
        sample = timer.stop()
        sample.ok = False
        sample.error = str(e)
        return sample, ""

    tokens_per_s = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns else 0.0
    sample = timer.stop(extra={"tokens": eval_count, "tokens_per_s": round(tokens_per_s, 2)})
    return sample, "".join(pieces)


def benchmark_model(label: str, model_id: str, cases: list[dict], system: str,
                    n_runs: int, available: set[str]) -> None:
    if model_id not in available and model_id.split(":")[0] not in {a.split(":")[0] for a in available}:
        print(f"  [SKIP] '{model_id}' no esta descargado. Ejecuta:  ollama pull {model_id}")
        return

    print(f"\n>>> Modelo: {label}  ({model_id})")
    for case in cases:
        cid = case["id"]
        total_runs = n_runs + (1 if config.DISCARD_WARMUP else 0)
        for run in range(1, total_runs + 1):
            warmup = config.DISCARD_WARMUP and run == 1
            sample, text = run_single(model_id, system, case["prompt"], case.get("max_tokens", 256))
            tag = "calentamiento" if warmup else f"corrida {run - (1 if config.DISCARD_WARMUP else 0)}"
            status = "OK" if sample.ok else f"ERROR ({sample.error[:40]})"
            ttft = f"{sample.ttft_s*1000:.0f} ms" if sample.ttft_s else "n/a"
            print(f"    {cid:24s} [{tag:14s}] TTFT={ttft:>9s}  total={sample.total_s:6.2f}s  {status}")

            append_row(RESULTS_CSV, make_row(
                category="LLM", service=label, test_case=cid, run_idx=run, warmup=warmup,
                sample=sample, metric_name="tokens_per_s",
                metric_value=sample.extra.get("tokens_per_s", ""),
                notes=f"tokens={sample.extra.get('tokens', '')}",
            ))
            dump_jsonl(RESULTS_JSONL, {
                "service": label, "model_id": model_id, "case": cid,
                "run": run, "warmup": warmup, "ttft_s": sample.ttft_s,
                "total_s": sample.total_s, "ok": sample.ok, "output": text,
            })


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de LLMs locales (Ollama).")
    parser.add_argument("--models", nargs="*", default=None,
                        help="Subconjunto de etiquetas de config.LLM_MODELS a evaluar.")
    parser.add_argument("--runs", type=int, default=config.N_RUNS,
                        help="Corridas a promediar por prompt (rubrica: >= 5).")
    args = parser.parse_args()

    data = json.loads(config.LLM_PROMPTS_FILE.read_text(encoding="utf-8"))
    system = data.get("system_prompt", "")
    cases = data["casos"]

    selected = config.LLM_MODELS
    if args.models:
        selected = {k: v for k, v in config.LLM_MODELS.items() if k in args.models}
        if not selected:
            print("Ninguna etiqueta valida. Disponibles:", list(config.LLM_MODELS))
            return

    available = list_available_models()
    print(f"Modelos descargados en Ollama: {sorted(available) or '(ninguno)'}")
    print(f"Corridas por prompt: {args.runs} (+1 calentamiento descartado)")

    for label, model_id in selected.items():
        benchmark_model(label, model_id, cases, system, args.runs, available)

    print(f"\nListo. Resultados crudos en: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
