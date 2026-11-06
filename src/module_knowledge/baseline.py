"""A deliberately simple, non-generative extraction floor for comparison."""

from __future__ import annotations

import hashlib


def extractive_baseline(frozen: dict, blocks: list[dict]) -> dict:
    if frozen["slice"] != "development":
        raise PermissionError("The extractive floor only runs on development sources")
    allowed = {source["id"]: source for source in frozen["sources"] if source["role"] not in {"gold", "student_style_gold", "style_gold"}}
    if len(allowed) != len(frozen["sources"]):
        raise ValueError("Gold cannot enter baseline inputs")
    items = []
    skipped = []
    for block in blocks:
        source = allowed.get(block["source_id"])
        if source is None or source["sha256"] != block["source_sha256"]:
            raise ValueError("Unfrozen source block")
        if block["quality_flags"] or not block["text"].strip():
            skipped.append({"source_id": block["source_id"], "locator": block["locator"], "reason": block["quality_flags"][0] if block["quality_flags"] else "no_extracted_text"})
            continue
        for index, line in enumerate(block["text"].splitlines()):
            if not line.strip():
                continue
            items.append(
                {
                    "id": hashlib.sha256(f"{block['source_id']}:{block['locator']}:{index}".encode()).hexdigest()[:20],
                    "text": line.strip(),
                    "source_id": block["source_id"],
                    "relative_path": block["relative_path"],
                    "locator": block["locator"],
                    "role": block["role"],
                    "visual_unreviewed": False,
                    "fact_checked": False,
                }
            )
    return {"module": frozen.get("module"), "slice": frozen["slice"], "model": "extractive-floor", "items": items, "skipped": skipped}
