"""
common/metrics.py
=================
Calculo de metricas de calidad y agregados estadisticos.

- Word Error Rate (WER) para evaluar la precision de transcripcion (STT).
- Real-Time Factor (RTF) para evaluar la eficiencia de sintesis (TTS).
- Agregados (media, desviacion estandar, percentil) sobre N corridas.
"""
from __future__ import annotations

import re
import statistics
import unicodedata
from typing import Sequence


# --------------------------------------------------------------------------
#  Normalizacion de texto (para comparar transcripcion vs referencia)
# --------------------------------------------------------------------------
def normalize_text(text: str, strip_accents: bool = False) -> str:
    """Normaliza texto para una comparacion WER justa.

    Pasa a minusculas, elimina puntuacion y colapsa espacios. Opcionalmente
    elimina acentos (algunos motores STT no los restituyen). Mantener este
    paso identico para todos los motores evita sesgar el WER.
    """
    text = text.lower().strip()
    if strip_accents:
        text = "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )
    text = re.sub(r"[^\w\sáéíóúñü]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_error_rate(reference: str, hypothesis: str, strip_accents: bool = False) -> float:
    """WER = (S + D + I) / N  mediante distancia de edicion a nivel de palabra.

    Usa la libreria `jiwer` si esta disponible; si no, recurre a una
    implementacion propia de Levenshtein por palabras (sin dependencias).
    """
    ref = normalize_text(reference, strip_accents)
    hyp = normalize_text(hypothesis, strip_accents)

    try:
        import jiwer  # type: ignore
        return float(jiwer.wer(ref, hyp))
    except Exception:
        pass  # fallback sin dependencias

    ref_w = ref.split()
    hyp_w = hyp.split()
    n = len(ref_w)
    if n == 0:
        return 0.0 if not hyp_w else 1.0

    # Programacion dinamica (Levenshtein a nivel de palabra).
    prev = list(range(len(hyp_w) + 1))
    for i, rw in enumerate(ref_w, 1):
        cur = [i] + [0] * len(hyp_w)
        for j, hw in enumerate(hyp_w, 1):
            cost = 0 if rw == hw else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1] / n


def real_time_factor(processing_s: float, audio_duration_s: float) -> float:
    """RTF = tiempo de procesamiento / duracion del audio.

    RTF < 1 significa mas rapido que tiempo real (deseable en TTS/STT
    interactivos). Devuelve inf si la duracion del audio es 0.
    """
    if audio_duration_s <= 0:
        return float("inf")
    return processing_s / audio_duration_s


# --------------------------------------------------------------------------
#  Agregados estadisticos sobre N corridas
# --------------------------------------------------------------------------
def aggregate(values: Sequence[float]) -> dict:
    """Devuelve media, desviacion estandar, min, max y p95 de una serie."""
    vals = [v for v in values if v is not None]
    if not vals:
        return {"mean": None, "std": None, "min": None, "max": None, "p95": None, "n": 0}
    vals_sorted = sorted(vals)
    p95_idx = max(0, int(round(0.95 * (len(vals_sorted) - 1))))
    return {
        "mean": statistics.fmean(vals),
        "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
        "min": min(vals),
        "max": max(vals),
        "p95": vals_sorted[p95_idx],
        "n": len(vals),
    }
