#!/usr/bin/env bash
# Genera report/reporte_tecnico.pdf desde el Markdown con Pandoc.
#
# El reporte usa emojis (🟣🔵🟢) y simbolos (≈, ±) que se ven bien en GitHub pero
# que las fuentes serif clasicas de LaTeX no contienen. Para un PDF academico
# limpio, este script crea una copia temporal sustituyendo esos glifos por su
# etiqueta de texto equivalente (que ya acompana a cada emoji en las tablas) y
# luego invoca Pandoc. El Markdown original NO se modifica.
#
# NOTA (Windows/OneDrive): Pandoc falla al preparar el directorio temporal de
# medios cuando la ruta del proyecto es larga y con espacios (p.ej. dentro de
# "OneDrive - ..."). Por eso el build se realiza en un directorio CORTO
# (BUILD_DIR, por defecto C:/pdfbuild) y luego se copia el PDF de vuelta.
#
# Requisitos: pandoc + un motor LaTeX (xelatex / tectonic). Si no hay LaTeX en el
# sistema, usa el binario portable de tectonic (ver README, seccion 7).
set -euo pipefail
cd "$(dirname "$0")"

SRC="reporte_tecnico.md"
OUT="reporte_tecnico.pdf"
ENGINE="${PDF_ENGINE:-tectonic}"        # exporta PDF_ENGINE=xelatex si lo prefieres
BUILD_DIR="${BUILD_DIR:-/c/pdfbuild}"   # ruta corta sin espacios (Git Bash + Windows)

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/figures"
cp figures/*.png "$BUILD_DIR/figures/" 2>/dev/null || true

# Sustituye emojis/simbolos no soportados por LaTeX y escribe una copia temporal
# en el directorio actual (ruta relativa, valida tambien para Python de Windows).
python - "$SRC" ".reporte_pdf.md" <<'PY'
import sys
src, tmp = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
for e in ("🟣 ", "🔵 ", "🟢 ", "🟣", "🔵", "🟢"):
    s = s.replace(e, "")
s = s.replace("≈", "~").replace("±", "+/-")
open(tmp, "w", encoding="utf-8").write(s)
PY
cp ".reporte_pdf.md" "$BUILD_DIR/r.md"
rm -f ".reporte_pdf.md"

( cd "$BUILD_DIR" && pandoc r.md -o r.pdf \
    --pdf-engine="$ENGINE" \
    -V lang=es -V geometry:margin=2.5cm \
    -V mainfont="Cambria" -V monofont="Consolas" )

cp "$BUILD_DIR/r.pdf" "$OUT"
rm -rf "$BUILD_DIR"
echo "PDF generado: $OUT"
