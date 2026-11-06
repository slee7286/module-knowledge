"""Consolidate generated points into a cited, hierarchical study-note outline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .preferences import preference_context

_CHILD_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "item_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "item_ids"],
    "additionalProperties": False,
}
_BULLET_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "item_ids": {"type": "array", "items": {"type": "string"}},
        "children": {"type": "array", "items": _CHILD_SCHEMA},
    },
    "required": ["text", "item_ids", "children"],
    "additionalProperties": False,
}
_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "heading": {"type": "string"},
        "bullets": {"type": "array", "items": _BULLET_SCHEMA},
    },
    "required": ["heading", "bullets"],
    "additionalProperties": False,
}
_OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {"sections": {"type": "array", "items": _SECTION_SCHEMA}},
    "required": ["sections"],
    "additionalProperties": False,
}
OUTLINE_PROMPT = (
    "Restructure the supplied extracted points as concise study notes in the student's style. "
    "Use clear, specific topic subheadings; short direct statements; and naturally nested bullets, "
    "with definitions, assumptions, reasoning, examples, and implications under the relevant main point. "
    "Keep the style close to the student's notes: direct phrasing such as 'We assume', 'For example', "
    "'This means', and 'Note' where natural; British spelling; no generic introductory prose. "
    "Merge repeated or overlapping points. Preserve every distinct definition, condition, step, exception, "
    "example, number, unit, and equation. Keep course logistics concise and grouped rather than repeated. "
    "Do not infer beyond the supplied points or add facts. Each input item ID must appear exactly once in "
    "an item's item_ids array. IDs are internal metadata and must never appear in headings or prose. Headings "
    "are organizational labels, not substitutes for content: if an input point suggests a heading, attach that "
    "point's ID to the nearest bullet. Return only the required JSON."
)


def _normalised_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def separate_repeated_items(
    items: list[dict],
    previously_covered: dict[str, str],
    current_group: str,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """Remove exact generated-point repeats from later groups, retaining their source references."""
    earlier = dict(previously_covered)
    retained = []
    repeats: dict[str, list[dict]] = {}
    for item in items:
        if item.get("exact_source_text"):
            retained.append(item)
            continue
        text = str(item.get("text", "")).strip()
        if not text or re.search(r"(?i)(?<![A-Za-z0-9])(?:source|sources)/", text):
            retained.append(item)
            continue
        key = _normalised_text(text)
        if key in earlier:
            repeats.setdefault(earlier[key], []).append(item)
        else:
            retained.append(item)
            previously_covered.setdefault(key, current_group)
    return retained, repeats


def deduplicate_items(items: list[dict]) -> list[dict]:
    """Collapse whitespace/case-identical points while retaining every provenance item."""
    unique: list[dict] = []
    indexes: dict[str, int] = {}
    for item in items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        key = _normalised_text(text)
        if key in indexes:
            unique[indexes[key]]["items"].append(item)
            continue
        node = {"id": f"u{len(unique) + 1:06d}", "text": text, "items": [item]}
        indexes[key] = len(unique)
        unique.append(node)
    return unique


def _support_items(item_ids: object, lookup: dict[str, dict], used: set[str]) -> list[dict]:
    if not isinstance(item_ids, list):
        return []
    result = []
    for item_id in item_ids:
        if isinstance(item_id, str) and item_id in lookup and item_id not in used:
            used.add(item_id)
            result.extend(lookup[item_id]["items"])
    return result


def _normalise_bullet(raw: object, lookup: dict[str, dict], used: set[str], *, allow_children: bool, restored: set[str]) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    text = raw.get("text")
    if not isinstance(text, str):
        return []
    text = re.sub(r"^\s*(?:u\d{6}|r\d+-\d{6})\s*:\s*", "", text).strip()
    if not text:
        return []
    id_pattern = r"\b(?:u\d{6}|r\d+-\d{6})\b"
    if re.search(id_pattern, text):
        remainder = re.sub(id_pattern, "", text).strip(" ,;:[]()\t\n")
        item_ids = raw.get("item_ids", [])
        if remainder or not isinstance(item_ids, list):
            return []
        valid_ids = list(dict.fromkeys(
            item_id for item_id in item_ids
            if isinstance(item_id, str) and item_id in lookup and item_id not in used
        ))
        if not valid_ids:
            return []
        text = " ".join(lookup[item_id]["text"] for item_id in valid_ids)
        restored.update(valid_ids)
    support_items = _support_items(raw.get("item_ids"), lookup, used)
    children = []
    if allow_children and isinstance(raw.get("children"), list):
        for child in raw["children"]:
            children.extend(_normalise_bullet(child, lookup, used, allow_children=False, restored=restored))
    if not support_items:
        return children
    return [{"text": text.strip(), "support_items": support_items, "children": children}]


def normalize_sections(raw_sections: object, input_nodes: list[dict]) -> tuple[list[dict], int]:
    """Validate model support IDs and restore any point the model left unassigned."""
    lookup = {node["id"]: node for node in input_nodes}
    used: set[str] = set()
    restored: set[str] = set()
    sections: list[dict] = []
    if isinstance(raw_sections, list):
        for raw_section in raw_sections:
            if not isinstance(raw_section, dict):
                continue
            heading = raw_section.get("heading")
            if not isinstance(heading, str) or not heading.strip():
                continue
            raw_bullets = raw_section.get("bullets", [])
            bullets = []
            if isinstance(raw_bullets, list):
                for raw_bullet in raw_bullets:
                    bullets.extend(_normalise_bullet(raw_bullet, lookup, used, allow_children=True, restored=restored))
            if bullets:
                sections.append({"heading": heading.strip(), "bullets": bullets})

    missing = [node for node in input_nodes if node["id"] not in used]
    if missing:
        additional = next((section for section in sections if section["heading"].casefold() == "additional points"), None)
        if additional is None:
            additional = {"heading": "Additional points", "bullets": []}
            sections.append(additional)
        additional["bullets"].extend(
            {"text": node["text"], "support_items": node["items"], "children": []}
            for node in missing
        )
    if not sections and input_nodes:
        sections = [{
            "heading": "Additional points",
            "bullets": [
                {"text": node["text"], "support_items": node["items"], "children": []}
                for node in input_nodes
            ],
        }]
        missing = input_nodes
    return merge_sections(sections), len(missing) + len(restored)


def _merge_support_items(left: list[dict], right: list[dict]) -> list[dict]:
    merged = list(left)
    seen = {
        (item.get("id"), item.get("source_id"), item.get("relative_path"), item.get("locator"))
        for item in merged
    }
    for item in right:
        key = (item.get("id"), item.get("source_id"), item.get("relative_path"), item.get("locator"))
        if key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def _merge_bullets(left: list[dict], right: list[dict]) -> list[dict]:
    merged = list(left)
    index = {_normalised_text(item["text"]): position for position, item in enumerate(merged)}
    for item in right:
        key = _normalised_text(item["text"])
        if key not in index:
            index[key] = len(merged)
            merged.append(item)
            continue
        target = merged[index[key]]
        target["support_items"] = _merge_support_items(target["support_items"], item["support_items"])
        target["children"] = _merge_bullets(target["children"], item["children"])
    return merged


def merge_sections(sections: list[dict]) -> list[dict]:
    """Merge equal headings and collapse exact repeated bullets across the whole note."""
    merged: list[dict] = []
    index: dict[str, int] = {}
    for section in sections:
        heading = str(section.get("heading", "")).strip()
        if not heading or not section.get("bullets"):
            continue
        key = _normalised_text(heading)
        if key not in index:
            index[key] = len(merged)
            merged.append({"heading": heading, "bullets": list(section["bullets"])})
        else:
            target = merged[index[key]]
            target["bullets"] = _merge_bullets(target["bullets"], section["bullets"])

    seen_bullets: dict[str, dict] = {}

    def add_bullets(
        existing: list[dict],
        candidates: list[dict],
        ancestors: tuple[dict, ...] = (),
    ) -> list[dict]:
        result = list(existing)
        ancestor_ids = {id(node) for node in ancestors}
        for candidate in candidates:
            key = _normalised_text(candidate["text"])
            if key in seen_bullets:
                target = seen_bullets[key]
                if target is candidate:
                    continue
                target["support_items"] = _merge_support_items(
                    target["support_items"], candidate["support_items"]
                )
                if id(target) in ancestor_ids:
                    result.extend(add_bullets([], candidate["children"], ancestors))
                else:
                    target["children"] = add_bullets(
                        target["children"], candidate["children"], (*ancestors, target)
                    )
                continue
            seen_bullets[key] = candidate
            candidate["children"] = add_bullets(
                [], candidate["children"], (*ancestors, candidate)
            )
            result.append(candidate)
        return result

    for section in merged:
        section["bullets"] = add_bullets([], section["bullets"])
    return [section for section in merged if section["bullets"]]


def _chunks(nodes: list[dict], *, max_items: int = 40, max_chars: int = 7000) -> list[list[dict]]:
    result: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for node in nodes:
        size = len(node["text"])
        if current and (len(current) >= max_items or current_chars + size > max_chars):
            result.append(current)
            current = []
            current_chars = 0
        current.append(node)
        current_chars += size
    if current:
        result.append(current)
    return result


def _request_outline(
    nodes: list[dict],
    *,
    context: str,
    endpoint: str,
    model: str,
    checkpoint_dir: Path,
    module: str | None = None,
) -> list[dict]:
    address = urlparse(endpoint)
    if address.scheme != "http" or address.hostname not in {"127.0.0.1", "::1"}:
        raise ValueError("Model endpoint must be HTTP on an explicit loopback address")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": OUTLINE_PROMPT + preference_context("outline", module=module)["prompt_suffix"]},
            {"role": "user", "content": json.dumps({"context": context, "items": [{"id": node["id"], "text": node["text"]} for node in nodes]}, ensure_ascii=False)},
        ],
        "format": _OUTLINE_SCHEMA,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 3000},
    }
    request_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    cache_key = hashlib.sha256(request_bytes).hexdigest()
    checkpoint = Path(checkpoint_dir) / f"{cache_key}.json"
    if checkpoint.is_file():
        response = json.loads(checkpoint.read_text(encoding="utf-8"))
    else:
        request = Request(endpoint.rstrip("/") + "/api/chat", request_bytes, {"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=300) as connection:
            response = json.load(connection)
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint.with_suffix(".tmp")
        temporary.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        temporary.replace(checkpoint)
    content = json.loads(response["message"]["content"])
    sections = content.get("sections")
    if not isinstance(sections, list):
        raise ValueError("Outline response does not contain a sections list")
    return sections


def _flatten_outline_nodes(sections: list[dict], pass_number: int) -> list[dict]:
    nodes = []

    def append(node: dict) -> None:
        nodes.append({
            "id": f"r{pass_number}-{len(nodes) + 1:06d}",
            "text": node["text"],
            "items": node["support_items"],
        })
        for child in node["children"]:
            append(child)

    for section in sections:
        for bullet in section["bullets"]:
            append(bullet)
    return nodes


def consolidate_items(
    items: list[dict],
    *,
    context: str,
    endpoint: str,
    model: str,
    checkpoint_dir: Path,
    module: str | None = None,
) -> dict:
    """Deduplicate and organize model-drafted items, preserving every source item."""
    generated = []
    metadata_items_removed = 0
    for item in items:
        text = str(item.get("text", "")).strip()
        if item.get("exact_source_text") or not text:
            continue
        if re.search(r"(?i)(?<![A-Za-z0-9])(?:source|sources)/", text):
            metadata_items_removed += 1
            continue
        generated.append(item)
    unique = deduplicate_items(generated)
    batch_errors = []
    fallback_counts = []
    sections = []
    current_nodes = unique
    passes = 0

    def request_batch(
        batch: list[dict], pass_number: int, batch_number: int, *, depth: int = 0
    ) -> tuple[list[dict], int]:
        try:
            response_sections = _request_outline(
                batch,
                context=f"{context}; outline pass {pass_number}, batch {batch_number}",
                endpoint=endpoint,
                model=model,
                checkpoint_dir=checkpoint_dir,
                module=module,
            )
        except Exception as error:
            failure = {
                "pass": pass_number,
                "batch": batch_number,
                "error_type": type(error).__name__,
            }
            batch_errors.append(failure)
            if isinstance(error, (ValueError, KeyError, TypeError)) and len(batch) > 10 and depth < 3:
                midpoint = len(batch) // 2
                left, left_fallbacks = request_batch(
                    batch[:midpoint], pass_number, batch_number, depth=depth + 1
                )
                right, right_fallbacks = request_batch(
                    batch[midpoint:], pass_number, batch_number, depth=depth + 1
                )
                fallback_count = left_fallbacks + right_fallbacks
                failure["recovered"] = fallback_count == 0
                return merge_sections(left + right), fallback_count
            response_sections = []
        return normalize_sections(response_sections, batch)

    for pass_number in range(1, 3):
        if not current_nodes:
            break
        max_items, max_chars = (40, 7000) if pass_number == 1 else (60, 9000)
        pass_sections = []
        pass_fallback_count = 0
        batches = _chunks(current_nodes, max_items=max_items, max_chars=max_chars)
        for batch_number, batch in enumerate(batches, start=1):
            normalised, fallback_count = request_batch(batch, pass_number, batch_number)
            pass_sections.extend(normalised)
            pass_fallback_count += fallback_count
        sections = merge_sections(pass_sections)
        fallback_counts.append(pass_fallback_count)
        passes = pass_number
        flattened = _flatten_outline_nodes(sections, pass_number)
        if pass_number == 2 or not flattened or (
            len(batches) == 1 and len(flattened) >= len(current_nodes)
        ):
            break
        current_nodes = flattened

    bullet_count = sum(
        len(section["bullets"])
        + sum(len(bullet["children"]) for bullet in section["bullets"])
        for section in sections
    )
    final_fallbacks = fallback_counts[-1] if fallback_counts else 0
    intermediate_fallbacks = sum(fallback_counts[:-1])
    return {
        "sections": sections,
        "stats": {
            "original_items": len(generated),
            "metadata_items_removed": metadata_items_removed,
            "unique_items": len(unique),
            "duplicates_removed": len(generated) - len(unique),
            "semantic_items_merged": max(0, len(unique) - bullet_count),
            "consolidated_bullets": bullet_count,
            "fallback_items": final_fallbacks,
            "intermediate_fallback_items": intermediate_fallbacks,
            "batch_errors": batch_errors,
            "passes": passes,
            "sections": len(sections),
        },
    }
