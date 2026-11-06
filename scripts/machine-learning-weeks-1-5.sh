#!/bin/sh
# Safe entry point: preview by default; generation requires the word run.
set -eu

if [ "$#" -gt 2 ]; then
  printf 'Usage: sh scripts/machine-learning-weeks-1-5.sh [preview|run] [fresh-run-name]\n' >&2
  exit 2
fi
MODE=${1:-preview}
NAME=${2:-weeks-1-5}
case "$MODE" in
  preview) set -- --dry-run ;;
  run) set -- ;;
  *) printf 'Mode must be preview or run.\n' >&2; exit 2 ;;
esac
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ROOT=${ONEDRIVE_ROOT:-/home/siheon/projects/OneDrive}
exec "$PROJECT/.venv/bin/module-knowledge" generate-y2 \
  --year-root "$ROOT" --output-root "$ROOT" --in-module-generated \
  --academic-year '2026--27' --module 'Machine Learning' --weeks 1-5 \
  --run-name "$NAME" "$@"
