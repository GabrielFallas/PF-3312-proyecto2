"""
analysis/plot_latency_cost.py
=============================
Genera el grafico de LATENCIA vs COSTO para los LLM (figura exigida por la
rubrica). Cruza la latencia total media empirica (de results/llm_results.csv)
con el costo de lista por millon de tokens de SALIDA de cada servicio.

Los modelos locales tienen costo 0 (offline), por lo que aparecen en el eje
x=0: el grafico evidencia visualmente que la opcion local es, a la vez, la mas
barata y de las mas rapidas.

Precios de lista (USD / 1M tokens de salida), junio 2026, capa gratuita aparte.
Fuentes citadas en el reporte (refs. [11]-[12]). Sujetos a cambio por proveedor.

    python -m analysis.plot_latency_cost
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# Costo de lista por 1M tokens de SALIDA (USD). 0.0 = local/offline.
COST_PER_1M_OUT = {
    "Gemini-2.5-Flash": 2.50,
    "Gemini-2.5-Flash-Lite": 0.40,
    "Groq-Llama-3.3-70B": 0.79,
    "Groq-GPT-OSS-120B": 0.60,
    "Groq-Llama-4-Scout": 0.34,
    "Llama-3.1-8B-local": 0.0,
    "Mistral-7B-local": 0.0,
    "Phi-3.5-local": 0.0,
    "Gemma-2-9B-local": 0.0,
    "Qwen-2.5-7B-local": 0.0,
}

CSV_PATH = config.RESULTS_DIR / "llm_results.csv"
OUT_PATH = config.ROOT / "report" / "figures" / "llm_latencia_vs_costo.png"


def mean_latency() -> dict[str, float]:
    acc = defaultdict(list)
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("warmup", "").lower() == "true" or row.get("ok", "").lower() != "true":
                continue
            try:
                acc[row["service"]].append(float(row["total_s"]))
            except (ValueError, KeyError):
                continue
    return {k: sum(v) / len(v) for k, v in acc.items() if v}


def main() -> None:
    lat = mean_latency()
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for svc, cost in COST_PER_1M_OUT.items():
        if svc not in lat:
            continue
        local = cost == 0.0
        ax.scatter(cost, lat[svc], s=90,
                   color="#2ca02c" if local else "#1f77b4",
                   edgecolor="black", zorder=3)
        ax.annotate(svc.replace("-local", ""), (cost, lat[svc]),
                    textcoords="offset points", xytext=(7, 4), fontsize=8)

    ax.set_xlabel("Costo de lista — USD por 1M tokens de salida\n(0 = local/offline; capa gratuita aparte)")
    ax.set_ylabel("Latencia total media (s) — menor es mejor")
    ax.set_title("LLM: latencia vs. costo\n(verde = local offline, azul = nube; jun. 2026)")
    ax.grid(True, alpha=0.3, zorder=0)
    # Leyenda manual
    ax.scatter([], [], color="#2ca02c", edgecolor="black", label="Local (offline, $0)")
    ax.scatter([], [], color="#1f77b4", edgecolor="black", label="Nube (free tier / pago)")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=130)
    print(f"Figura -> {OUT_PATH}")


if __name__ == "__main__":
    main()
