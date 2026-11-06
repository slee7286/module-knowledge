"""Anchored, lossy-aware extraction of frozen official sources."""

from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
import tempfile
from typing import cast

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def extract_source(source: dict) -> list[dict]:
    path = Path(source["local_path"])
    if path.suffix.lower() in {".txt", ".py"}:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        blocks = []
        chunk: list[str] = []
        chunk_start = 1
        chunk_size = 0
        for line_number, line in enumerate(lines, start=1):
            if chunk and chunk_size + len(line) + 1 > 4500:
                block = {
                    "source_id": source["id"],
                    "source_sha256": source["sha256"],
                    "role": source["role"],
                    "locator": f"lines {chunk_start}--{line_number - 1}",
                    "text": "\n".join(chunk),
                    "method": "python-source" if path.suffix.lower() == ".py" else "utf8-lines",
                    "quality_flags": [],
                }
                if path.suffix.lower() == ".py":
                    block["language"] = "python"
                blocks.append(block)
                chunk = []
                chunk_start = line_number
                chunk_size = 0
            chunk.append(line)
            chunk_size += len(line) + 1
        if chunk:
            block = {
                "source_id": source["id"],
                "source_sha256": source["sha256"],
                "role": source["role"],
                "locator": f"lines {chunk_start}--{len(lines)}",
                "text": "\n".join(chunk),
                "method": "python-source" if path.suffix.lower() == ".py" else "utf8-lines",
                "quality_flags": [],
            }
            if path.suffix.lower() == ".py":
                block["language"] = "python"
            blocks.append(block)
        return blocks
    if path.suffix.lower() == ".docx":
        document = Document(str(path))
        blocks = []
        paragraph_number = 0
        table_number = 0
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                paragraph_number += 1
                flags = ["needs_visual_review"] if item._p.xpath(".//w:drawing") or item._p.xpath(".//m:oMath") else []
                if not item.text.strip() and not flags:
                    continue
                locator = f"paragraph {paragraph_number}"
                text = item.text.strip()
                style = item.style.name if item.style is not None else "Normal"
            elif isinstance(item, Table):
                table_number += 1
                locator = f"table {table_number}"
                text = "\n".join(" | ".join(cell.text for cell in row.cells) for row in item.rows)
                flags = ["needs_visual_review"] if item._tbl.xpath(".//w:drawing") else []
                style = "Table"
            else:
                continue
            blocks.append(
                {
                    "source_id": source["id"],
                    "source_sha256": source["sha256"],
                    "role": source["role"],
                    "locator": locator,
                    "text": text,
                    "method": "python-docx",
                    "style": style,
                    "quality_flags": flags,
                }
            )
        return blocks
    if path.suffix.lower() == ".pptx":
        deck = Presentation(str(path))
        slides = []
        for slide_number, slide in enumerate(deck.slides, start=1):
            parts = []
            visual = False
            for shape in slide.shapes:
                if shape.has_text_frame and getattr(shape, "text_frame").text.strip():
                    parts.append(getattr(shape, "text_frame").text.strip())
                if shape.has_table:
                    parts.extend(" | ".join(cell.text for cell in row.cells) for row in getattr(shape, "table").rows)
                if shape.shape_type in {MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.CHART}:
                    visual = True
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame
                if notes is not None and notes.text.strip():
                    parts.append("Speaker notes: " + notes.text.strip())
            text = "\n".join(parts)
            numeric_values = re.findall(r"(?<!\w)[£$]?\(?\d[\d,.]*\)?%?", text)
            if len(numeric_values) >= 8:
                visual = True  # flattened multi-column budgets cannot be trusted as prose
            slides.append(
                {
                    "source_id": source["id"],
                    "source_sha256": source["sha256"],
                    "role": source["role"],
                    "locator": f"slide {slide_number}",
                    "text": text,
                    "method": "python-pptx",
                    "quality_flags": ["needs_visual_review"] if visual or not text else [],
                }
            )
        return slides
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported source format: {path.suffix}")
    blocks = []
    with pymupdf.open(path) as document:
        for page_number in range(1, document.page_count + 1):
            page = document.load_page(page_number - 1)
            text = cast(str, page.get_text("text", sort=True)).strip()
            flags = []
            if len(text) < 30:
                flags.append("needs_ocr")
            if page.get_images() or page.get_drawings() or len(text) < 30:
                flags.append("needs_visual_review")
            blocks.append(
                {
                    "source_id": source["id"],
                    "source_sha256": source["sha256"],
                    "role": source["role"],
                    "locator": f"p.{page_number}",
                    "text": text,
                    "method": "pymupdf-text",
                    "quality_flags": flags,
                }
            )
    return blocks


def extract_frozen(frozen: dict, output_path: Path) -> dict:
    """Atomically write source-anchored blocks, retaining low-quality pages."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".evidence-", dir=output.parent)
    counts: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    rows = []
    try:
        for source in frozen["sources"]:
            blocks = extract_source(source)
            counts[source["id"]] += len(blocks)
            for block in blocks:
                block["relative_path"] = source["relative_path"]
                rows.append(block)
        questions = {" ".join(block["text"].split()) for block in rows if block["role"] == "tutorial_question" and block["text"].strip()}
        for block in rows:
            if block["role"] == "tutorial_solution" and " ".join(block["text"].split()) in questions:
                block["quality_flags"].append("needs_visual_answer_review")
            flags.update(block["quality_flags"])
        with os.fdopen(descriptor, "w", encoding="utf-8") as writer:
            for block in rows:
                writer.write(json.dumps(block, ensure_ascii=False) + "\n")
        os.replace(temporary, output)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return {"slice": frozen["slice"], "source_count": len(counts), "blocks": sum(counts.values()), "flags": dict(flags), "per_source": dict(counts)}
