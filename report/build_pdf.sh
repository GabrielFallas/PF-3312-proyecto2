#!/usr/bin/env bash
# Genera report/reporte_tecnico.pdf desde el Markdown con Pandoc.
#
# El reporte usa emojis (🟣🔵🟢) y simbolos (≈, ±) que se ven bien en GitHub pero
# que las fuentes serif clasicas de LaTeX no contienen. Para un PDF academico
# limpio, este script crea una copia temporal sustituyendo esos glifos por su
# etiqueta de texto equivalente (que ya acompana a cada emoji en las tablas) y
# luego invoca Pandoc. El Markdown original NO se modifica.
#
# Requisitos: pandoc + un motor LaTeX (xelatex / tectonic). Si no hay LaTeX en el
# sistema, se puede usar el binario portable de tectonic (ver README, seccion 7).
set -euo pipefail
cd "$(dirname "$0")"

SRC="reporte_tecnico.md"
TMP=".reporte_pdf.md"
OUT="reporte_tecnico.pdf"
ENGINE="${PDF_ENGINE:-tectonic}"   # exporta PDF_ENGINE=xelatex si lo prefieres

python - "$SRC" "$TMP" <<'PY'
import sys
src, tmp = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
for e in ("🟣 ", "🔵 ", "🟢 ", "🟣", "🔵", "🟢"):
    s = s.replace(e, "")
s = s.replace("≈", "~").replace("±", "+/-")
open(tmp, "w", encoding="utf-8").write(s)
PY

pandoc "$TMP" -o "$OUT" \
  --pdf-engine="$ENGINE" \
  -V lang=es -V geometry:margin=2.5cm \
  -V mainfont="Cambria" -V monofont="Consolas"

rm -f "$TMP"
echo "PDF generado: $OUT"
