#!/usr/bin/env python3
"""Repeatable, local-only English transcription with pinned Whisper weights."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

from faster_whisper import WhisperModel

MODEL_REPO = "Systran/faster-whisper-medium.en"
MODEL_REVISION = "a29b04bd15381511a9af671baec01072039215e3"
OPTIONS = {
    "language": "en",
    "task": "transcribe",
    "beam_size": 5,
    "temperature": 0.0,
    "condition_on_previous_text": True,
    "vad_filter": False,
    "word_timestamps": False,
    "compression_ratio_threshold": 2.4,
    "log_prob_threshold": -1.0,
    "no_speech_threshold": 0.6,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    os.umask(0o077)
    audio = args.audio.resolve(strict=True)
    model_dir = args.model_dir.resolve(strict=True)
    if not (model_dir / "model.bin").is_file():
        parser.error(f"Pinned model files missing in {model_dir}")
    audio_hash_before = sha256(audio)
    model = WhisperModel(
        str(model_dir),
        device="cpu",
        compute_type="int8",
        cpu_threads=8,
        num_workers=1,
    )
    segments, info = model.transcribe(str(audio), **OPTIONS)
    lines = [
        "# Local AI-podcast transcript",
        f"# Audio file: {audio.name}",
        f"# Audio SHA-256: {audio_hash_before}",
        f"# ASR model: {MODEL_REPO}@{MODEL_REVISION}",
        "# Runtime: Python " + ".".join(map(str, sys.version_info[:3]))
        + "; faster-whisper " + importlib.metadata.version("faster-whisper")
        + "; CTranslate2 " + importlib.metadata.version("ctranslate2")
        + "; PyAV " + importlib.metadata.version("av"),
        "# Decoding: CPU, int8, 8 threads; beam search; temperature 0; VAD disabled",
        f"# Detected language: {info.language} (probability {info.language_probability:.4f})",
        "# Segment timestamps are approximate; review technical terms against the slides.",
        "",
    ]
    count = 0
    for segment in segments:
        text = segment.text.strip()
        if text:
            lines.append(f"[{stamp(segment.start)} - {stamp(segment.end)}] {text}")
            count += 1
    if sha256(audio) != audio_hash_before:
        raise RuntimeError("Source audio changed during transcription")
    if count == 0:
        raise RuntimeError("No speech segments were produced")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(
        json.dumps(
            {
                "output": str(output),
                "segments": count,
                "audio_sha256": audio_hash_before,
                "model": f"{MODEL_REPO}@{MODEL_REVISION}",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
