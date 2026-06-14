"""
analysis/build_report_data.py
=============================
Consolida los CSV crudos (results/*.csv) producidos por los benchmarks y
genera artefactos listos para incluir en el reporte tecnico:

  1. Tablas resumidas en Markdown (media +/- desv. de latencia, TTFT, WER, RTF)
     -> report/tablas_generadas.md
  2. Graficos de dispersion "latencia vs metrica de calidad" por categoria
     -> report/figures/*.png

Las corridas de calentamiento (warmup=True) se EXCLUYEN de los promedios,
cumpliendo el requisito de promediar >= 5 ejecuciones limpias.

Uso:
    python -m analysis.build_report_data
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta pandas. Instala dependencias: pip install -r requirements.txt")

FIG_DIR = config.ROOT / "report" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLES_MD = config.ROOT / "report" / "tablas_generadas.md"


def load(category_csv: Path) -> pd.DataFrame:
    if not category_csv.exists():
        return pd.DataFrame()
    df = pd.read_csv(category_csv)
    # Normaliza el booleano de warmup (viene como texto "True"/"False").
    df["warmup"] = df["warmup"].astype(str).str.lower().isin(["true", "1"])
    df["ok"] = df["ok"].astype(str).str.lower().isin(["true", "1"])
    return df[(~df["warmup"]) & (df["ok"])].copy()


def summarize(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """media y desviacion estandar de una columna numerica por servicio."""
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    g = df.groupby("service")[value_col]
    return pd.DataFrame({"mean": g.mean(), "std": g.std(ddof=0), "n": g.count()})


def md_table(title: str, summary: dict[str, pd.DataFrame]) -> str:
    """Construye una tabla Markdown 'servicio x metricas (media +/- std)'."""
    services = sorted({s for d in summary.values() for s in d.index})
    headers = ["Servicio"] + list(summary.keys())
    lines = [f"### {title}", "", "| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for svc in services:
        cells = [svc]
        for metric_df in summary.values():
            if svc in metric_df.index:
                m, s = metric_df.loc[svc, "mean"], metric_df.loc[svc, "std"]
                cells.append(f"{m:.3f} ± {s:.3f}" if pd.notna(m) else "—")
            else:
                cells.append("—")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def scatter(df: pd.DataFrame, x: str, y: str, title: str, fname: str,
            xlabel: str, ylabel: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df[x] = pd.to_numeric(df[x], errors="coerce")
    df[y] = pd.to_numeric(df[y], errors="coerce")
    agg = df.groupby("service").agg({x: "mean", y: "mean"}).dropna()
    if agg.empty:
        print(f"  [aviso] sin datos para el grafico '{title}'")
        return

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(agg[x], agg[y], s=90, color="#3b82f6", edgecolor="white", zorder=3)
    for svc, row in agg.iterrows():
        ax.annotate(svc, (row[x], row[y]), fontsize=8,
                    xytext=(6, 4), textcoords="offset points")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out = FIG_DIR / fname
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  grafico -> {out.relative_to(config.ROOT)}")


def main() -> None:
    sections: list[str] = ["# Tablas y figuras generadas automaticamente\n",
                           "_Generado por `analysis/build_report_data.py` a partir de los CSV crudos. "
                           "Excluye corridas de calentamiento._\n"]

    # ---------------- LLM ----------------
    llm = load(config.RESULTS_DIR / "llm_results.csv")
    if not llm.empty:
        summary = {
            "Latencia total (s)": summarize(llm, "total_s"),
            "TTFT (s)": summarize(llm, "ttft_s"),
            "Tokens/seg": summarize(llm, "metric_value"),
        }
        sections.append(md_table("LLM — latencia y velocidad", summary))
        scatter(llm.assign(tps=pd.to_numeric(llm["metric_value"], errors="coerce")),
                "ttft_s", "tps", "LLM: TTFT vs velocidad de generacion",
                "llm_ttft_vs_tps.png", "TTFT (s, menor es mejor)", "Tokens/seg (mayor es mejor)")
    else:
        sections.append("### LLM\n\n_Sin datos: ejecuta `python -m benchmarks.llm_benchmark`._\n")

    # ---------------- STT ----------------
    stt = load(config.RESULTS_DIR / "stt_results.csv")
    if not stt.empty:
        summary = {
            "Latencia (s)": summarize(stt, "total_s"),
            "WER": summarize(stt, "metric_value"),
        }
        sections.append(md_table("STT — latencia y precision", summary))
        scatter(stt.assign(wer=pd.to_numeric(stt["metric_value"], errors="coerce")),
                "total_s", "wer", "STT: latencia vs WER",
                "stt_latencia_vs_wer.png", "Latencia (s, menor es mejor)", "WER (menor es mejor)")
    else:
        sections.append("### STT\n\n_Sin datos: ejecuta `python -m benchmarks.stt_benchmark`._\n")

    # ---------------- TTS ----------------
    tts = load(config.RESULTS_DIR / "tts_results.csv")
    if not tts.empty:
        summary = {
            "Latencia sintesis (s)": summarize(tts, "total_s"),
            "RTF": summarize(tts, "metric_value"),
        }
        sections.append(md_table("TTS — latencia y eficiencia (RTF)", summary))
        scatter(tts.assign(rtf=pd.to_numeric(tts["metric_value"], errors="coerce")),
                "total_s", "rtf", "TTS: latencia vs RTF",
                "tts_latencia_vs_rtf.png", "Latencia de sintesis (s)", "RTF (menor es mejor)")
    else:
        sections.append("### TTS\n\n_Sin datos: ejecuta `python -m benchmarks.tts_benchmark`._\n")

    TABLES_MD.write_text("\n".join(sections), encoding="utf-8")
    print(f"\nTablas Markdown -> {TABLES_MD.relative_to(config.ROOT)}")
    print(f"Figuras        -> {FIG_DIR.relative_to(config.ROOT)}/")
    print("\nIncluye estas tablas/figuras en report/reporte_tecnico.md antes de exportar a PDF.")


if __name__ == "__main__":
    main()
