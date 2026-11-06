#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  printf 'Usage: sh scripts/build-pdf.sh /path/to/notes.tex\n' >&2
  exit 2
fi

TEX=$(realpath "$1")
ENGINE=${TECTONIC:-"$HOME/.local/share/module-knowledge/tools/tectonic-0.17.0/tectonic"}
EXPECTED='Tectonic 0.17.0'

[ -f "$TEX" ] || { printf 'LaTeX source not found: %s\n' "$TEX" >&2; exit 2; }
[ -x "$ENGINE" ] || { printf 'Pinned Tectonic binary not found; run scripts/install-tectonic.sh.\n' >&2; exit 2; }
[ "$("$ENGINE" --version)" = "$EXPECTED" ] || {
  printf 'Expected %s at %s.\n' "$EXPECTED" "$ENGINE" >&2
  exit 2
}
exec "$ENGINE" --keep-logs --keep-intermediates --reruns 2 --outdir "$(dirname "$TEX")" "$TEX"
