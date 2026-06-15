"""
benchmarks/llm_benchmark.py
===========================
Banco de pruebas para Modelos de Lenguaje (LLM).

Evalua un catalogo BALANCEADO (config.LLM_SERVICES) que combina:
  - Nube alta gama   : Gemini 2.5 Pro (free tier devuelve 429), gpt-oss-120B y
                       Llama 4 Scout (Groq)
  - Nube bajo costo  : Gemini 2.5 Flash/Flash-Lite, Groq Llama 3.3 70B
  - Local offline    : Llama/Mistral/Phi/Gemma/Qwen via Ollama

Mide, para cada modelo y prompt controlado, en modo *streaming*:
  - TTFT (Time To First Token), latencia total y tokens/seg.

Los servicios en la nube se ACTIVAN solo si su API key esta en el entorno
(.env); de lo contrario se omiten. Promedia N_RUNS corridas (descartando la
de calentamiento) y persiste cada ejecucion en results/llm_results.csv.

Uso:
    python -m benchmarks.llm_benchmark
    python -m benchmarks.llm_benchmark --services Groq-GPT-OSS-120B Phi-3.5-local
    python -m benchmarks.llm_benchmark --only-local
    python -m benchmarks.llm_benchmark --runs 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from common.persistence import append_row, dump_jsonl, make_row
from common.timer import StreamTimer

RESULTS_CSV = config.RESULTS_DIR / "llm_results.csv"
RESULTS_JSONL = config.RESULTS_DIR / "llm_raw.jsonl"


# --------------------------------------------------------------------------
#  Adaptadores por proveedor. Cada uno ejecuta UNA generacion en streaming
#  y devuelve (LatencySample, texto). Marcan el TTFT en el primer fragmento.
# --------------------------------------------------------------------------
def run_ollama(svc: dict, system: str, prompt: str, max_tokens: int):
    timer = StreamTimer()
    payload = {
        "model": svc["model"], "prompt": prompt, "system": system, "stream": True,
        "options": {"num_predict": max_tokens, "temperature": 0.0},
    }
    pieces, eval_count, eval_dur_ns = [], 0, 0
    timer.start()
    try:
        with requests.post(f"{config.OLLAMA_HOST}/api/generate",
                           json=payload, stream=True, timeout=300) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("response"):
                    timer.mark_first_token()
                    pieces.append(chunk["response"])
                if chunk.get("done"):
                    eval_count = chunk.get("eval_count", 0) or 0
                    eval_dur_ns = chunk.get("eval_duration", 0) or 0
    except (requests.RequestException, json.JSONDecodeError) as e:
        s = timer.stop(); s.ok = False; s.error = str(e)
        return s, ""
    tps = (eval_count / (eval_dur_ns / 1e9)) if eval_dur_ns else 0.0
    return timer.stop(extra={"tokens": eval_count, "tokens_per_s": round(tps, 2)}), "".join(pieces)


def run_openai_compat(svc: dict, system: str, prompt: str, max_tokens: int):
    """Cubre cualquier API compatible con OpenAI (Groq, OpenAI, OpenRouter, ...)."""
    timer = StreamTimer()
    headers = {"Authorization": f"Bearer {config.get_key(svc)}", "Content-Type": "application/json",
               "User-Agent": config.HTTP_USER_AGENT}
    payload = {
        "model": svc["model"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.0, "stream": True,
        "stream_options": {"include_usage": True},
    }
    pieces, tokens = [], 0
    timer.start()
    try:
        with requests.post(f"{svc['base_url']}/chat/completions",
                           headers=headers, json=payload, stream=True, timeout=300) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                obj = json.loads(data)
                if obj.get("usage"):
                    tokens = obj["usage"].get("completion_tokens", 0) or tokens
                for ch in obj.get("choices", []):
                    delta = ch.get("delta", {}).get("content")
                    if delta:
                        timer.mark_first_token()
                        pieces.append(delta)
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        s = timer.stop(); s.ok = False; s.error = str(e)
        return s, ""
    s = timer.stop()
    tps = (tokens / s.total_s) if (tokens and s.total_s) else 0.0
    s.extra = {"tokens": tokens, "tokens_per_s": round(tps, 2)}
    return s, "".join(pieces)


def run_gemini(svc: dict, system: str, prompt: str, max_tokens: int):
    """Google Gemini via REST streamGenerateContent (SSE)."""
    timer = StreamTimer()
    # La API key se envia por HEADER (x-goog-api-key), nunca en la URL, para que
    # no pueda filtrarse a logs ni a mensajes de error/CSV.
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{svc['model']}:streamGenerateContent?alt=sse")
    headers = {"User-Agent": config.HTTP_USER_AGENT, "x-goog-api-key": config.get_key(svc)}
    gen_cfg = {"maxOutputTokens": max_tokens, "temperature": 0.0}
    # Modelos "thinking" (Gemini 2.5 Pro/Flash) razonan antes de responder. Si el
    # servicio define thinking_budget, se topa para conservar cuota y garantizar
    # que quede presupuesto para texto visible (necesario para medir el TTFT).
    if svc.get("thinking_budget") is not None:
        gen_cfg["thinkingConfig"] = {"thinkingBudget": svc["thinking_budget"]}
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    pieces, tokens = [], 0
    timer.start()
    try:
        with requests.post(url, json=payload, stream=True, timeout=300,
                           headers=headers) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                obj = json.loads(line[len("data:"):].strip())
                for cand in obj.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        if part.get("text"):
                            timer.mark_first_token()
                            pieces.append(part["text"])
                if obj.get("usageMetadata"):
                    tokens = obj["usageMetadata"].get("candidatesTokenCount", 0) or tokens
    except (requests.RequestException, json.JSONDecodeError) as e:
        s = timer.stop(); s.ok = False; s.error = str(e)
        return s, ""
    s = timer.stop()
    tps = (tokens / s.total_s) if (tokens and s.total_s) else 0.0
    s.extra = {"tokens": tokens, "tokens_per_s": round(tps, 2)}
    return s, "".join(pieces)


DISPATCH = {
    "ollama": run_ollama,
    "openai_compat": run_openai_compat,
    "gemini": run_gemini,
}


def ollama_available() -> set[str]:
    try:
        r = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=10)
        r.raise_for_status()
        return {m["name"] for m in r.json().get("models", [])}
    except requests.RequestException:
        return set()


def benchmark_service(label: str, svc: dict, cases: list[dict], system: str,
                      n_runs: int, ollama_models: set[str]) -> None:
    # Filtro de disponibilidad.
    if not config.has_key(svc):
        print(f"  [SKIP] {label}: falta {svc.get('key_env')} en .env (no se evalua).")
        return
    if svc["provider"] == "ollama":
        base = svc["model"].split(":")[0]
        if svc["model"] not in ollama_models and base not in {m.split(':')[0] for m in ollama_models}:
            print(f"  [SKIP] {label}: modelo no descargado. Ejecuta: ollama pull {svc['model']}")
            return

    fn = DISPATCH[svc["provider"]]
    is_cloud = svc.get("kind") == "cloud"
    # En la nube usamos menos corridas (conservar cuota) y topamos los tokens de
    # salida para que las pruebas no agoten el free tier.
    runs_here = config.CLOUD_N_RUNS if is_cloud else n_runs
    print(f"\n>>> {label}  [{svc['tier']}]"
          + (f"  (nube: {runs_here} corridas, max {config.CLOUD_MAX_OUTPUT_TOKENS} tokens)" if is_cloud else ""))
    total_runs = runs_here + (1 if config.DISCARD_WARMUP else 0)
    for case in cases:
        cid = case["id"]
        max_tokens = case.get("max_tokens", 256)
        if is_cloud:
            max_tokens = min(max_tokens, config.CLOUD_MAX_OUTPUT_TOKENS)
        for run in range(1, total_runs + 1):
            warmup = config.DISCARD_WARMUP and run == 1
            sample, text = fn(svc, system, case["prompt"], max_tokens)
            tag = "calentamiento" if warmup else f"corrida {run - (1 if config.DISCARD_WARMUP else 0)}"
            ttft = f"{sample.ttft_s*1000:.0f} ms" if sample.ttft_s else "n/a"
            status = "OK" if sample.ok else f"ERR({sample.error[:32]})"
            print(f"    {cid:24s} [{tag:14s}] TTFT={ttft:>9s}  total={sample.total_s:6.2f}s  {status}")
            append_row(RESULTS_CSV, make_row(
                "LLM", label, cid, run, warmup, sample,
                metric_name="tokens_per_s", metric_value=sample.extra.get("tokens_per_s", ""),
                notes=f"tier={svc['tier']}; tokens={sample.extra.get('tokens','')}",
            ))
            dump_jsonl(RESULTS_JSONL, {
                "service": label, "tier": svc["tier"], "case": cid, "run": run,
                "warmup": warmup, "ttft_s": sample.ttft_s, "total_s": sample.total_s,
                "ok": sample.ok, "output": text,
            })
            # Respeta el limite de peticiones/min del free tier (no afecta la medicion).
            if svc.get("kind") == "cloud" and config.CLOUD_REQUEST_DELAY:
                time.sleep(config.CLOUD_REQUEST_DELAY)


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark de LLMs (nube + local).")
    p.add_argument("--services", nargs="*", default=None,
                   help="Subconjunto de etiquetas de config.LLM_SERVICES.")
    p.add_argument("--only-local", action="store_true", help="Solo modelos locales (Ollama).")
    p.add_argument("--runs", type=int, default=config.N_RUNS)
    args = p.parse_args()

    data = json.loads(config.LLM_PROMPTS_FILE.read_text(encoding="utf-8"))
    system, cases = data.get("system_prompt", ""), data["casos"]

    selected = dict(config.LLM_SERVICES)
    if args.services:
        selected = {k: v for k, v in selected.items() if k in args.services}
    if args.only_local:
        selected = {k: v for k, v in selected.items() if v["kind"] == "local"}

    ollama_models = ollama_available()
    print(f"Modelos en Ollama: {sorted(ollama_models) or '(ninguno)'}")
    print(f"Corridas por prompt: {args.runs} (+1 calentamiento descartado)")

    for label, svc in selected.items():
        benchmark_service(label, svc, cases, system, args.runs, ollama_models)

    print(f"\nListo. Resultados crudos en: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
