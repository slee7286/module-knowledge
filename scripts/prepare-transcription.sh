#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VENV=${MODULE_KNOWLEDGE_ASR_VENV:-"$HOME/.local/share/module-knowledge/tools/whisper-env"}
MODEL_DIR=${MODULE_KNOWLEDGE_WHISPER_MODEL:-"$HOME/.local/share/module-knowledge/models/faster-whisper-medium.en"}
MODEL_REPO=Systran/faster-whisper-medium.en
MODEL_REVISION=a29b04bd15381511a9af671baec01072039215e3

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -r "$ROOT/tools/transcription-requirements.lock"
"$VENV/bin/hf" download "$MODEL_REPO" --revision "$MODEL_REVISION" --local-dir "$MODEL_DIR"
test -s "$MODEL_DIR/model.bin"
printf 'Ready: %s\nModel: %s@%s\n' "$VENV" "$MODEL_REPO" "$MODEL_REVISION"
