"""Freeze selected official sources without making a gold-note retrieval path."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def freeze_slice(
    config_path: Path,
    source_root: Path,
    private_root: Path,
    slice_name: str,
    *,
    unlock_test: bool = False,
) -> dict:
    if slice_name == "locked_test" and not unlock_test:
        raise PermissionError("Locked test requires an explicit unlock after development is frozen")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    selected = config["slices"][slice_name]["sources"]
    root = Path(source_root).resolve(strict=True)
    out = Path(private_root).resolve()
    if out == root or root in out.parents:
        raise ValueError("Private outputs must not be written into the source collection")

    rows = []
    for item in selected:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or not item.get("role"):
            raise ValueError(f"Invalid official source: {relative}")
        filename = relative.name.casefold()
        module = config.get("module", "Accounting").casefold()
        if item["role"] in {"student_style_gold", "style_gold", "gold"} or filename == f"{module} notes.docx":
            raise ValueError("Student gold notes cannot enter the generator snapshot")
        source = (root / relative).resolve(strict=True)
        if not source.is_file() or not source.is_relative_to(root):
            raise ValueError(f"Source outside selected module: {relative}")

        source_id = hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()[:20]
        (out / "sources").mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".copy-", dir=out / "sources")
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
                while chunk := reader.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    writer.write(chunk)
            destination = out / "sources" / f"{source_id}-{digest.hexdigest()[:16]}{source.suffix.lower()}"
            if destination.exists():
                Path(temporary).unlink()
            else:
                os.replace(temporary, destination)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()
        rows.append(
            {
                "id": source_id,
                "relative_path": relative.as_posix(),
                "role": item["role"],
                "sha256": digest.hexdigest(),
                "size": size,
                "local_path": str(destination),
            }
        )
    frozen = {"module": config.get("module"), "slice": slice_name, "sources": rows}
    target = out / f"frozen-{slice_name}.json"
    serialized = json.dumps(frozen, indent=2, ensure_ascii=False) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != serialized:
        raise ValueError("Frozen source set has changed; use a new private run directory")
    target.write_text(serialized, encoding="utf-8")
    return frozen
