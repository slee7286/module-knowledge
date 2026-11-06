"""Gold-safe, diagnostic-only evaluation. Never supplies gold text to drafting."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def _metrics(paragraphs: list[dict], *, tables: int = 0) -> dict:
    styles = Counter(p["style"] for p in paragraphs)
    return {
        "paragraphs": len(paragraphs),
        "words": sum(len(p["text"].split()) for p in paragraphs),
        "heading_1": styles["Heading 1"],
        "heading_2": styles["Heading 2"],
        "list_paragraphs": sum(n for style, n in styles.items() if style.startswith("List")),
        "drawings": sum(p["drawings"] for p in paragraphs),
        "tables": tables,
    }


def extract_gold_sections(path: Path, *, label: str) -> dict:
    """Open gold only inside the evaluator; return solely requested sections."""
    requested = {part.strip() for part in label.split(" + ")}
    if not requested or not all(re.fullmatch(r"(?:Lecture|Tutorial) \d+", part) for part in requested):
        raise ValueError("Expected a precise lecture/tutorial pair label")
    document = Document(str(path))
    active = False
    found = set()
    paragraphs: list[dict] = []
    table_count = 0
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            style = block.style.name if block.style is not None else "Normal"
            if style == "Heading 1":
                match = re.match(r"^((?:Lecture|Tutorial)\s+\d+)\b", block.text)
                active = bool(match and match.group(1) in requested)
                if active and match:
                    found.add(match.group(1))
            if active and block.text.strip():
                paragraphs.append({"text": block.text.strip(), "style": style, "drawings": len(block._p.xpath(".//w:drawing"))})
            elif active and block._p.xpath(".//w:drawing"):
                paragraphs.append({"text": "", "style": style, "drawings": len(block._p.xpath(".//w:drawing"))})
        elif isinstance(block, Table) and active:
            table_count += 1
    if found != requested:
        raise ValueError(f"Missing gold sections: {sorted(requested - found)}")
    return {"label": label, "paragraphs": paragraphs, "metrics": _metrics(paragraphs, tables=table_count)}


def _latex_metrics(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"(?m)(?<!\\)%.*$", "", source)
    headings_1 = len(re.findall(r"\\section\*?\{", source))
    headings_2 = len(re.findall(r"\\subsection\*?\{", source))
    list_items = len(re.findall(r"\\item\b", source))
    figures = len(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{", source))
    tables = len(re.findall(r"\\begin\{(?:tabular|longtable)\}", source))
    equations = len(re.findall(r"\\begin\{(?:equation|align|gather)\*?\}", source))
    visible = re.sub(r"\\[A-Za-z]+\*?(?:\[[^]]*\])?", " ", source)
    visible = re.sub(r"[{}$]", " ", visible)
    words = re.findall(r"\b[\w'-]+\b", visible, flags=re.UNICODE)
    return {
        "paragraphs": sum(bool(line.strip()) for line in visible.splitlines()),
        "words": len(words),
        "heading_1": headings_1,
        "heading_2": headings_2,
        "list_paragraphs": list_items,
        "drawings": figures,
        "tables": tables,
        "equations": equations,
    }


def evaluate_candidate(gold: dict, candidate_path: Path, sidecar: dict, evidence: list[dict]) -> dict:
    if Path(candidate_path).suffix.lower() != ".tex":
        raise ValueError("Generated note candidates must be LaTeX (.tex)")
    candidate_metrics = _latex_metrics(Path(candidate_path))
    known = {(b["source_id"], b["locator"]) for b in evidence}
    seen = {(item["source_id"], item["locator"]) for item in sidecar["items"]}
    invalid = sorted(seen - known)
    eligible = {(b["source_id"], b["locator"]) for b in evidence if b["text"].strip()}
    return {
        "content_coverage_status": "ungraded_requires_human_review",
        "gold_metrics": gold["metrics"],
        "candidate_metrics": candidate_metrics,
        "citation_integrity": {"invalid_locator_count": len(invalid), "invalid_locators": invalid},
        "block_touch_diagnostic": {"referenced_source_blocks": len(seen & eligible), "nonempty_source_blocks": len(eligible)},
        "fact_checked_items": sum(bool(item["fact_checked"]) for item in sidecar["items"]),
        "visual_unreviewed_items": sidecar.get("unreviewed_visual_items", 0),
        "skipped_blocks": len(sidecar["skipped"]),
        "gate": "not_passed",
        "reason": "No human-reviewed atomic coverage/faithfulness/style ratings; automatic locator checks do not verify facts.",
    }
