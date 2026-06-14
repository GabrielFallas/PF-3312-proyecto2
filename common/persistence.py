"""
common/persistence.py
=====================
Persistencia de los datos empiricos recolectados.

Cada corrida individual se anexa a un CSV (formato largo: una fila por
ejecucion) y, opcionalmente, a un JSON Lines con el detalle completo. El
formato largo facilita luego el analisis con pandas y la generacion de
tablas/graficos sin perder ninguna medicion cruda.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Patrones de API keys de los proveedores usados. Sirven como RED DE SEGURIDAD:
# cualquier valor que coincida se enmascara antes de escribirse a disco, para que
# una key no pueda filtrarse a un CSV/JSON via un mensaje de error.
_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),        # Google API key
    re.compile(r"AQ\.[A-Za-z0-9_\-]{20,}"),       # Google AI Studio key (formato nuevo)
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),          # Groq
    re.compile(r"sk_[A-Za-z0-9]{20,}"),           # ElevenLabs / OpenAI-style
    re.compile(r"(?i)(key|token|api[_-]?key)=[^&\s\"]+"),  # parametros key=... en URLs
]


def redact(value):
    """Enmascara cualquier API key detectada en una cadena."""
    if not isinstance(value, str):
        return value
    for pat in _SECRET_PATTERNS:
        value = pat.sub("***REDACTED***", value)
    return value

CSV_FIELDS = [
    "timestamp",      # ISO-8601 UTC
    "category",       # LLM | STT | TTS
    "service",        # etiqueta del modelo/motor
    "test_case",      # id del prompt/audio/texto de prueba
    "run_idx",        # numero de corrida (1..N)
    "warmup",         # True si fue corrida de calentamiento (excluida del promedio)
    "total_s",        # latencia total (s)
    "ttft_s",         # time-to-first-token (s) o vacio
    "metric_name",    # nombre de la metrica de calidad (wer | rtf | tokens_per_s | ...)
    "metric_value",   # valor de dicha metrica
    "ok",             # True/False
    "error",          # mensaje de error si aplica
    "notes",          # texto libre (hardware, tamano de modelo, etc.)
]


def append_row(csv_path: Path, row: dict) -> None:
    """Anexa una fila al CSV, escribiendo el encabezado si el archivo es nuevo."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not csv_path.exists()
    safe = {k: redact(row.get(k, "")) for k in CSV_FIELDS}
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(safe)


def append_rows(csv_path: Path, rows: Iterable[dict]) -> None:
    for r in rows:
        append_row(csv_path, r)


def dump_jsonl(jsonl_path: Path, record: dict) -> None:
    """Guarda el detalle completo (incluida la salida del modelo) en JSON Lines."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(redact(json.dumps(record, ensure_ascii=False)) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_row(category: str, service: str, test_case: str, run_idx: int,
             warmup: bool, sample, metric_name: str = "", metric_value="",
             notes: str = "") -> dict:
    """Construye una fila CSV a partir de un LatencySample (common.timer)."""
    return {
        "timestamp": now_iso(),
        "category": category,
        "service": service,
        "test_case": test_case,
        "run_idx": run_idx,
        "warmup": warmup,
        "total_s": round(sample.total_s, 6),
        "ttft_s": round(sample.ttft_s, 6) if sample.ttft_s is not None else "",
        "metric_name": metric_name,
        "metric_value": metric_value,
        "ok": sample.ok,
        "error": sample.error,
        "notes": notes,
    }
