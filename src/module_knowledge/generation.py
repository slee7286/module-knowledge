"""End-to-end local generation of source-backed Year 2 LaTeX notes."""

from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote

import pymupdf

from .draft import SYSTEM_PROMPT, draft_slice
from .extract import extract_source
from .latex import _escape_tex, _strip_literal_source_path_lines, combine_latex_notes, render_latex
from .outline import OUTLINE_PROMPT, consolidate_items, separate_repeated_items
from .visual import VISUAL_PROMPT, recover_pdf_page
from .preferences import preference_context

_SUPPORTED_SUFFIXES = {".pdf", ".docx", ".pptx", ".txt", ".py"}
_IGNORED_DIRS = {".git", "__pycache__", "notes", "generated", "readings", "exams", "administrative material"}
_EXACT_TUTORIAL_ROLES = {"tutorial_question", "tutorial_solution", "tutorial_handout", "tutorial_code", "mock_question", "mock_solution"}
_PRESERVED_PDF_ROLES = _EXACT_TUTORIAL_ROLES | {"supplementary_material", "study_guide"}


def discover_source_groups(module_root: Path) -> list[dict]:
    """Find dated lecture/tutorial folders; ignore readings, exams, and video/audio."""
    root = Path(module_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Module source root must be a directory")
    course_roots = [root / name for name in ("source", "sources") if (root / name).is_dir()]
    groups: dict[tuple[str, str], set[Path]] = {}
    for course_root in course_roots:
        for base, directories, filenames in os.walk(course_root, followlinks=False):
            directories[:] = sorted(
                directory
                for directory in directories
                if directory.casefold() not in _IGNORED_DIRS
                and not (Path(base) / directory).is_symlink()
            )
            relative_parts = Path(base).relative_to(root).parts
            category_index = next(
                (index for index, part in enumerate(relative_parts) if part.casefold() in {"lectures", "tutorials"}),
                None,
            )
            if category_index is None:
                continue
            category = relative_parts[category_index].casefold()
            kind = "lecture" if category == "lectures" else "tutorial"
            event_parts = relative_parts[: min(category_index + 2, len(relative_parts))]
            event_relative = Path(*event_parts).as_posix()
            eligible = groups.setdefault((kind, event_relative), set())
            for filename in filenames:
                path = Path(base) / filename
                if path.suffix.casefold() not in _SUPPORTED_SUFFIXES or path.is_symlink():
                    continue
                eligible.add(path)
    results = []
    for (kind, relative_dir), files in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1].casefold())):
        if not files:
            continue
        results.extend(
            _split_source_group(
                {
                    "kind": kind,
                    "relative_dir": relative_dir,
                    "files": sorted(files, key=lambda path: path.name.casefold()),
                }
            )
        )
    return sorted(results, key=lambda group: (group["kind"], group["relative_dir"].casefold(), int(group["number"])))


def _source_number(kind: str, path: Path) -> int | None:
    if kind == "lecture":
        match = re.search(r"lecture\s*0*(\d+)", path.stem, re.IGNORECASE)
    else:
        match = re.search(r"(?:(?<![a-z0-9])ps\s*|problem\s*set\s*|tutorial\s*notes?\s*)0*(\d+)", path.stem, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _split_source_group(group: dict) -> list[dict]:
    numbered: dict[int, list[Path]] = {}
    unnumbered: list[Path] = []
    for path in group["files"]:
        number = _source_number(group["kind"], path)
        if number is None:
            unnumbered.append(path)
        else:
            numbered.setdefault(number, []).append(path)
    if len(numbered) <= 1:
        folder_match = re.search(r"_(\d+)$", Path(group["relative_dir"]).name)
        number = next(iter(numbered), int(folder_match.group(1)) if folder_match else 1)
        return [{**group, "number": str(number), "review_flags": []}]
    preferred = 0 if group["kind"] == "tutorial" and 0 in numbered else 1 if group["kind"] == "lecture" and 1 in numbered else min(numbered)
    results = []
    for number, files in sorted(numbered.items()):
        review_flags = []
        if number == preferred and unnumbered:
            files = [*files, *unnumbered]
            review_flags.append(
                f"Unnumbered supporting source(s) grouped with item {number} based on the shared date folder; confirm relevance"
            )
        results.append(
            {
                **group,
                "number": str(number),
                "files": sorted(files, key=lambda path: path.name.casefold()),
                "review_flags": review_flags,
            }
        )
    return results


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gvfs_source_uri(source_path: Path, mount_listing: str) -> str:
    """Map a mounted OneDrive path to its GIO URI without printing account data."""
    path = Path(source_path)
    mount_index = next(
        (index for index, part in enumerate(path.parts) if part.startswith("onedrive:")),
        None,
    )
    if mount_index is None:
        raise ValueError("Source is not under a mounted OneDrive GVfs path")
    attributes = dict(
        re.findall(r"(host|user)=([^,]+)", path.parts[mount_index])
    )
    identity = " ".join(attributes.values()).casefold()
    for line in mount_listing.splitlines():
        match = re.match(r"Mount\(\d+\):\s*(.*?)\s*->\s*(onedrive://\S+)", line)
        if match and all(value.casefold() in match.group(1).casefold() for value in attributes.values()):
            relative = Path(*path.parts[mount_index + 1 :]).as_posix()
            return match.group(2).rstrip("/") + "/" + quote(relative, safe="/")
    raise ValueError(f"No mounted OneDrive URI matches this GVfs account ({identity})")


def _source_role(kind: str, path: Path) -> str:
    filename = path.name.casefold()
    if kind == "lecture":
        if path.suffix.casefold() == ".txt" or any(word in filename for word in ("caption", "transcript", "audio overview")):
            return "lecture_transcript"
        return "lecture_slides" if path.suffix.casefold() in {".pdf", ".pptx"} else "lecture_handout"
    if path.suffix.casefold() == ".py":
        return "tutorial_code"
    if any(word in filename for word in ("solution", "answer", "mark scheme", "marking")):
        return "tutorial_solution"
    if re.search(r"(?:(?<![a-z0-9])ps\s*\d|problem\s*set|problem\s*sheet|questions?)", filename):
        return "tutorial_question"
    if path.suffix.casefold() in {".docx", ".pdf", ".pptx"}:
        return "tutorial_handout"
    return "tutorial_resource"


def _stage_group(
    group: dict,
    module_root: Path,
    snapshot_root: Path,
    *,
    copy_timeout: int,
) -> tuple[list[dict], list[dict]]:
    staged = []
    failures = []
    gvfs_sources = any(any(part.startswith("onedrive:") for part in path.parts) for path in group["files"])
    mount_listing = ""
    if gvfs_sources:
        gio = shutil.which("gio")
        if gio:
            try:
                mount_listing = subprocess.run(
                    [gio, "mount", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                ).stdout
            except (OSError, subprocess.SubprocessError):
                mount_listing = ""
    for source_path in group["files"]:
        relative = source_path.relative_to(module_root)
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".source-", dir=destination.parent)
        os.close(descriptor)
        try:
            if any(part.startswith("onedrive:") for part in source_path.parts):
                gio = shutil.which("gio")
                if not gio or not mount_listing:
                    raise OSError("No usable GIO OneDrive mount listing")
                source_uri = _gvfs_source_uri(source_path, mount_listing)
                Path(temporary).unlink()
                command = [gio, "copy", source_uri, temporary]
            else:
                command = ["cp", "--", str(source_path), temporary]
            copied = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=copy_timeout,
                check=False,
            )
            if copied.returncode != 0:
                raise OSError(copied.stderr.strip() or f"cp exited {copied.returncode}")
            actual_hash = _file_sha256(Path(temporary))
            if destination.is_file() and _file_sha256(destination) == actual_hash:
                Path(temporary).unlink()
            else:
                os.replace(temporary, destination)
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(
                {
                    "relative_path": relative.as_posix(),
                    "reason": "source-copy-timeout" if isinstance(error, subprocess.TimeoutExpired) else "source-copy-failed",
                    "detail": type(error).__name__,
                }
            )
            continue
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()
        staged.append(
            {
                "id": hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()[:20],
                "relative_path": relative.as_posix(),
                "role": group.get("source_roles", {}).get(relative.as_posix(), _source_role(group["kind"], source_path)),
                "sha256": actual_hash,
                "local_path": str(destination.resolve()),
            }
        )
    return staged, failures


def _date_number_title(
    group: dict,
    module_root: Path,
    *,
    academic_year: str | None = None,
) -> tuple[str, str, str, list[str]]:
    event_name = Path(group["relative_dir"]).name
    folder_match = re.search(r"(20\d{2}-\d{2}-\d{2})", event_name)
    review_flags: list[str] = list(group.get("review_flags", []))
    filename_dates = sorted(
        {
            match.group(0)
            for source in group["files"]
            for match in re.finditer(r"20\d{2}-\d{2}-\d{2}", source.name)
        }
    )
    if folder_match:
        folder_date = folder_match.group(1)
        try:
            parsed = date.fromisoformat(folder_date)
            display_date = parsed.strftime("%-d %B %Y")
        except ValueError:
            display_date = f"DATE NEEDS REVIEW ({folder_date})"
            review_flags.append(f"Unparseable date in source folder name: {folder_date}")
        conflicting = [value for value in filename_dates if value != folder_date]
        if conflicting:
            display_date = f"DATE NEEDS REVIEW (folder {folder_date}; source filename {', '.join(conflicting)})"
            review_flags.append(
                f"Date discrepancy: source folder says {folder_date}, while source filename(s) say {', '.join(conflicting)}"
            )
        if academic_year:
            year_values = [int(value) for value in re.findall(r"20\d{2}", academic_year)]
            short_end = re.search(r"20\d{2}\s*(?:--|-|/)\s*(\d{2})\b", academic_year)
            if short_end and year_values:
                year_values.append((year_values[0] // 100) * 100 + int(short_end.group(1)))
            if year_values and int(folder_date[:4]) not in set(year_values):
                existing_detail = f"; source filename {', '.join(conflicting)}" if conflicting else ""
                display_date = (
                    f"DATE NEEDS REVIEW (folder {folder_date}{existing_detail}; "
                    f"outside academic year {academic_year})"
                )
                review_flags.append(
                    f"Date discrepancy: folder date {folder_date} falls outside academic year {academic_year}"
                )
    else:
        display_date = "DATE NEEDS REVIEW"
        review_flags.append("No explicit date was found in the source folder name")

    number = group.get("number")
    if number is None:
        number_match = re.search(r"_(\d+)$", event_name)
        if not number_match:
            pattern = r"(?:lecture|week|ps|problem\s*set)\s*0*(\d+)"
            number_match = next(
                (match for source in group["files"] if (match := re.search(pattern, source.stem, re.IGNORECASE))),
                None,
            )
        number = str(int(number_match.group(1))) if number_match else None
    if number is None:
        number = "?"
        review_flags.append(f"Could not determine {group['kind']} number from source names")

    if group["kind"] == "lecture":
        title = "Lecture materials"
        explicit_numbers = sorted(
            {
                int(match.group(1))
                for source in group["files"]
                if (match := re.search(r"lecture\s*0*(\d+)", source.stem, re.IGNORECASE))
            }
        )
        if len(explicit_numbers) > 1:
            review_flags.append(
                "This date folder contains multiple lecture labels "
                + ", ".join(map(str, explicit_numbers))
                + "; review whether the materials should be separate notes"
            )
    else:
        problem_sets = sorted(
            {
                match.group(1)
                for source in group["files"]
                if (match := re.search(r"(?:(?<![a-z0-9])ps|problem\s*set)\s*0*(\d+)", source.stem, re.IGNORECASE))
            },
            key=int,
        )
        title = f"Problem Set {int(problem_sets[0])} materials" if len(problem_sets) == 1 else "Tutorial materials"
    if group.get("date"):
        mapped_date = date.fromisoformat(group["date"])
        if folder_match and folder_match.group(1) != group["date"]:
            review_flags.append(f"Mapped teaching date {group['date']} differs from folder date {folder_match.group(1)}")
        display_date = mapped_date.strftime("%-d %B %Y")
        review_flags = [flag for flag in review_flags if flag != "No explicit date was found in the source folder name"]
    if group["kind"] not in {"lecture", "tutorial"}:
        from .inventory import KIND_LABELS
        title = KIND_LABELS[group["kind"]] + " materials"
        if group.get("weeks"):
            title += " — weeks " + ", ".join(map(str, group["weeks"]))
        if not folder_match and not group.get("date"):
            display_date = "Date not supplied"
    return number, title, display_date, review_flags


def _recover_or_skip(block: dict, source: dict, endpoint: str, visual_model: str, checkpoints: Path) -> tuple[dict | None, str | None]:
    flags = block.get("quality_flags", [])
    if "needs_visual_answer_review" in flags:
        return None, "official-answer-visual-review-required"
    if "needs_ocr" in flags or not block.get("text", "").strip():
        if Path(source["local_path"]).suffix.casefold() == ".pdf" and block.get("locator", "").startswith("p."):
            try:
                return recover_pdf_page(
                    source,
                    block,
                    endpoint=endpoint,
                    model=visual_model,
                    checkpoint_dir=checkpoints / "visual",
                ), None
            except Exception as error:
                return None, f"visual-transcription-failed:{type(error).__name__}"
        return None, "no-extractable-text"
    return block, None


def _item_from_block(block: dict, text: str, *, exact: bool = False) -> dict:
    flags = block.get("quality_flags", [])
    return {
        "id": hashlib.sha256(f"{block['source_id']}:{block['locator']}:{text}".encode("utf-8")).hexdigest()[:20],
        "text": text.strip(),
        "source_id": block["source_id"],
        "relative_path": block["relative_path"],
        "locator": block["locator"],
        "role": block["role"],
        "visual_unreviewed": bool({"needs_visual_review", "visual_model_unverified"} & set(flags)),
        "fact_checked": False,
        "exact_source_text": exact,
    }


def _draft_group_items(
    frozen: dict,
    blocks: list[dict],
    *,
    endpoint: str,
    model: str,
    visual_model: str,
    checkpoint_dir: Path,
    progress_label: str,
) -> tuple[list[dict], list[dict]]:
    sources_by_id = {source["id"]: source for source in frozen["sources"]}
    items: list[dict] = []
    skipped: list[dict] = []
    total = len(blocks)
    for index, original in enumerate(blocks, start=1):
        source = sources_by_id[original["source_id"]]
        block = dict(original)
        if source["role"] in _EXACT_TUTORIAL_ROLES and Path(source["local_path"]).suffix.casefold() == ".pdf":
            # Exact PDFs are rendered as original pages, including image-only pages.
            # Do not ask a model to transcribe or solve them.
            if block.get("text", "").strip():
                items.append(_item_from_block(block, block["text"], exact=True))
            continue
        block, reason = _recover_or_skip(block, source, endpoint, visual_model, checkpoint_dir)
        if block is None:
            skipped.append({"source_id": source["id"], "locator": original["locator"], "reason": reason or "unreadable"})
            continue
        if source["role"] in _EXACT_TUTORIAL_ROLES:
            items.append(_item_from_block(block, block["text"], exact=True))
        else:
            quality_flags = [
                flag
                for flag in block.get("quality_flags", [])
                if flag not in {"needs_visual_review", "needs_ocr"}
            ]
            if "needs_visual_review" in original.get("quality_flags", []) and "visual_model_unverified" not in quality_flags:
                quality_flags.append("visual_model_unverified")
            block["quality_flags"] = quality_flags
            try:
                result = draft_slice(
                    frozen,
                    [block],
                    endpoint=endpoint,
                    model=model,
                    checkpoint_dir=checkpoint_dir / "draft",
                )
            except Exception as error:
                skipped.append(
                    {"source_id": source["id"], "locator": original["locator"], "reason": f"local-model-failed:{type(error).__name__}"}
                )
                continue
            items.extend(result["items"])
            skipped.extend(result["skipped"])
            if not result["items"] and not result["skipped"]:
                skipped.append({"source_id": source["id"], "locator": original["locator"], "reason": "model-returned-no-notes"})
        if index % 10 == 0 or index == total:
            print(f"  {progress_label}: processed {index}/{total} evidence blocks", flush=True)
    return items, skipped


def _source_citation(item: dict, source_by_id: dict[str, dict]) -> str:
    source = source_by_id[item["source_id"]]
    return rf" \sourcecite{{{_escape_tex(item['relative_path'])}}}{{{_escape_tex(item['locator'])}}}"


def _outline_fragment(outline: list[dict], source_by_id: dict[str, dict], *, include_sources: bool) -> list[str]:
    output = []

    def append_bullet(node: dict, depth: int) -> None:
        text = _strip_literal_source_path_lines(str(node.get("text", ""))).strip()
        if not text:
            return
        support_items = node.get("support_items", [])
        citations = []
        review = False
        if include_sources:
            seen_citations = set()
            for item in support_items:
                key = (item.get("relative_path"), item.get("locator"))
                if key not in seen_citations:
                    seen_citations.add(key)
                    citations.append(_source_citation(item, source_by_id))
                review = review or bool(item.get("visual_unreviewed"))
        suffix = "".join(citations)
        if review:
            suffix += r" \reviewflag{visual review pending}"
        indent = "    " * depth
        output.append(f"{indent}\\item {_escape_tex(text)}{suffix}")
        children = [child for child in node.get("children", []) if child.get("text", "").strip()]
        if children:
            output.append(f"{indent}\\begin{{itemize}}")
            for child in children:
                append_bullet(child, depth + 1)
            output.append(f"{indent}\\end{{itemize}}")

    for section in outline:
        heading = str(section.get("heading", "")).strip()
        bullets = section.get("bullets", [])
        if not heading or not bullets:
            continue
        output.extend([rf"\subsection{{{_escape_tex(heading)}}}", r"\begin{itemize}"])
        for bullet in bullets:
            append_bullet(bullet, 0)
        output.append(r"\end{itemize}")
    return output


def _prepare_tutorial_pages(sources: list[dict], note_dir: Path) -> list[dict]:
    """Keep original PDF questions, notation, tables, diagrams, and provided solutions."""
    pages = []
    for source in sources:
        if source["role"] not in _PRESERVED_PDF_ROLES or Path(source["local_path"]).suffix.casefold() != ".pdf":
            continue
        with pymupdf.open(source["local_path"]) as document:
            for number in range(1, document.page_count + 1):
                page = document.load_page(number - 1)
                text = str(page.get_text("text"))
                if source["role"] == "mock_solution":
                    label = "Provided official mock test solution"
                elif source["role"] == "mock_question":
                    label = "Mock test question"
                elif source["role"] == "supplementary_material":
                    label = "Supplementary material"
                elif source["role"] == "study_guide":
                    label = "Midterm study guide"
                elif source["role"] == "tutorial_solution" or re.search(r"(?im)^\s*solutions?\s*$", text):
                    label = "Provided official tutorial solution"
                elif source["role"] == "tutorial_question" or re.search(r"(?im)^\s*(?:exercise|problem)\b", text):
                    label = "Tutorial question"
                else:
                    label = "Tutorial handout"
                token = hashlib.sha256(source["relative_path"].encode("utf-8")).hexdigest()[:20]
                asset = f"pages/{token}-p{number}.png"
                destination = note_dir / asset
                destination.parent.mkdir(parents=True, exist_ok=True)
                page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), alpha=False).save(destination)
                pages.append({
                    "source_id": source["id"], "relative_path": source["relative_path"],
                    "locator": f"p.{number}", "label": label, "asset": asset,
                    "local_path": str(destination.resolve()), "sha256": _file_sha256(destination),
                })
    return pages


def _tutorial_pages_fragment(pages: list[dict], *, include_sources: bool) -> str:
    if not pages:
        return ""
    output = [r"\clearpage", r"\subsection{Original source pages}"]
    for index, page in enumerate(pages):
        if index:
            output.append(r"\clearpage")
        output.append(rf"\paragraph{{{_escape_tex(page['label'])} ({_escape_tex(page['locator'])}).}}")
        output.append(r"\begin{center}")
        output.append(
            r"\includegraphics[width=\linewidth,height=0.78\textheight,keepaspectratio]{\detokenize{"
            + page["local_path"] + "}}"
        )
        output.append(r"\end{center}")
        if include_sources:
            output.append(rf"\sourcecite{{{_escape_tex(page['relative_path'])}}}{{{_escape_tex(page['locator'])}}}")
    return "\n".join(output) + "\n"


def _body_fragment(
    items: list[dict],
    skipped: list[dict],
    source_by_id: dict[str, dict],
    *,
    include_sources: bool = True,
    outline: list[dict] | None = None,
) -> str:
    if not include_sources:
        output: list[str] = []
        if outline is not None:
            output.extend(_outline_fragment(outline, source_by_id, include_sources=False))
        else:
            generated = [
                _strip_literal_source_path_lines(item["text"]).strip()
                for item in items
                if not item.get("exact_source_text")
            ]
            generated = [text for text in generated if text]
            if generated:
                output.extend([r"\subsection{Notes}", r"\begin{itemize}"])
                output.extend(rf"\item {_escape_tex(text)}" for text in generated)
                output.append(r"\end{itemize}")
        exact_headings = {
            "tutorial_question": "Question text.",
            "tutorial_solution": "Official solution text.",
            "tutorial_handout": "Tutorial handout text.",
            "tutorial_code": "Python code.",
        }
        exact_items = [item for item in items if item.get("exact_source_text")]
        if exact_items:
            output.append(r"\subsection{Questions and solutions}")
        for item in exact_items:
            exact_text = item["text"]
            if not exact_text.strip():
                continue
            output.append(rf"\paragraph{{{exact_headings.get(item['role'], 'Notes.')}}}")
            output.extend(["% BEGIN EXACT SOURCE", r"\begin{quote}\small"])
            if item["role"] == "tutorial_code":
                output.append(r"\ttfamily")
            for line in exact_text.splitlines() or [exact_text]:
                output.append(_escape_tex(line) + r"\newline" if line.strip() else r"\par")
            output.extend([r"\end{quote}", "% END EXACT SOURCE"])
        has_note_text = bool(outline) if outline is not None else any(
            not item.get("exact_source_text") and _strip_literal_source_path_lines(item["text"]).strip()
            for item in items
        )
        if not has_note_text and not exact_items:
            output.append(r"\reviewflag{No note text was generated; review this section before use.}")
        return "\n".join(output) + "\n"

    output: list[str] = []
    if outline is not None:
        output.extend(_outline_fragment(outline, source_by_id, include_sources=True))
        exact_items = [item for item in items if item.get("exact_source_text")]
        if exact_items:
            output.append(r"\subsection{Questions and solutions}")
        source_items_by_path = {}
        for item in exact_items:
            source_items_by_path.setdefault(item["relative_path"], []).append(item)
        exact_groups = source_items_by_path.items()
    else:
        exact_groups = []
        by_path: dict[str, list[dict]] = {}
        for item in items:
            by_path.setdefault(item["relative_path"], []).append(item)
        for relative_path, source_items in by_path.items():
            output.append(rf"\subsection{{{_escape_tex(Path(relative_path).name)}}}")
            generated = [
                (item, _strip_literal_source_path_lines(item["text"]).strip())
                for item in source_items
                if not item.get("exact_source_text")
                and _strip_literal_source_path_lines(item["text"]).strip()
            ]
            if generated:
                output.append(r"\begin{itemize}")
                for item, text in generated:
                    review = r" \reviewflag{visual review pending}" if item["visual_unreviewed"] else ""
                    output.append(rf"\item {_escape_tex(text)}{_source_citation(item, source_by_id)}{review}")
                output.append(r"\end{itemize}")
            exact_groups.append((relative_path, [item for item in source_items if item.get("exact_source_text")]))
    for relative_path, source_items in exact_groups:
        for item in source_items:
            exact_text = item["text"]
            if not exact_text.strip():
                continue
            role = item["role"]
            heading = {
                "tutorial_question": "Question text from the source",
                "tutorial_solution": "Solution text from the source",
                "tutorial_handout": "Tutorial handout text",
                "tutorial_code": "Python source from the tutorial",
            }.get(role, "Source text")
            output.append(rf"\paragraph{{{heading} ({_escape_tex(item['locator'])}).}}")
            output.extend(["% BEGIN EXACT SOURCE", r"\begin{quote}\small"])
            if role == "tutorial_code":
                output.append(r"\ttfamily")
            lines = exact_text.splitlines() or [exact_text]
            for line in lines:
                if line.strip():
                    output.append(_escape_tex(line) + r"\newline")
                else:
                    output.append(r"\par")
            output.extend([r"\end{quote}", "% END EXACT SOURCE"])
            output.append(_source_citation(item, source_by_id))
            if item["visual_unreviewed"]:
                output.append(r"\reviewflag{visual material on this page has not been independently checked}")
    if skipped:
        output.extend([r"\section*{Source coverage and review gaps}", r"\begin{itemize}"])
        for item in skipped:
            relative_path = source_by_id.get(item["source_id"], {}).get(
                "relative_path", item.get("relative_path", item["source_id"])
            )
            descriptor = f"{relative_path}, {item['locator']}: {item['reason']}"
            output.append(rf"\item {_escape_tex(descriptor)}")
        output.append(r"\end{itemize}")
    if not items:
        output.append(r"\reviewflag{No note text was generated; inspect the source files and extraction gaps before use.}")
    return "\n".join(output) + "\n"


def _group_manifest_path(group: dict, notes_root: Path) -> Path:
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(group["relative_dir"]).name).strip("-") or "undated"
    return notes_root / f"{group['kind']}-{group['number']}-{token}"


def _compile_pdf(tex_path: Path, project_root: Path) -> dict:
    script = project_root / "scripts" / "build-pdf.sh"
    try:
        result = subprocess.run(
            ["sh", str(script), str(tex_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "pdf": str(tex_path.with_suffix(".pdf"))}
    return {
        "status": "ok" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "pdf": str(tex_path.with_suffix(".pdf")),
        "log": result.stdout[-4000:] + result.stderr[-4000:],
    }


def generate_module(
    module_root: Path,
    output_root: Path,
    *,
    academic_year: str,
    endpoint: str = "http://127.0.0.1:11434",
    model: str = "qwen3:8b",
    visual_model: str = "qwen3-vl:8b-instruct",
    compile_pdfs: bool = True,
    project_root: Path | None = None,
    in_module_generated: bool = False,
    source_plan: dict | None = None,
    run_name: str | None = None,
) -> dict:
    module_root = Path(module_root).resolve(strict=True)
    output_root = Path(output_root).resolve()
    module = module_root.name
    groups = source_plan["groups"] if source_plan is not None else discover_source_groups(module_root)
    if not groups:
        return {"module": module, "groups": [], "status": "no-lecture-or-tutorial-sources"}
    safe_module = re.sub(r"[^A-Za-z0-9_-]+", "-", module).strip("-") or "module"
    if in_module_generated:
        if output_root != module_root.parent:
            raise ValueError("The output root must be the Year 2 root for module-generated output")
        module_output = (module_root / "generated").resolve()
        if module_output.parent != module_root:
            raise ValueError("The module generated directory must be a direct child of the source module")
    else:
        if output_root == module_root or module_root in output_root.parents:
            raise ValueError("Generated notes must not be written into the source module")
        module_output = output_root / safe_module
        if not module_output.resolve().is_relative_to(output_root):
            raise ValueError("Output directory must not escape the output root through a symlink")
    if run_name:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_name):
            raise ValueError("Invalid run name")
        module_output = module_output / "runs" / run_name
        anchor = module_root if in_module_generated else output_root
        if not module_output.resolve().is_relative_to(anchor):
            raise ValueError("Output directory must not escape its root through a symlink")
        # Atomic reservation also protects against simultaneous launches.
        module_output.parent.mkdir(parents=True, exist_ok=True)
        module_output.mkdir(exist_ok=False)
    snapshot_root = module_output / "snapshot"
    notes_root = module_output / "notes"
    checkpoints = module_output / "checkpoints"
    module_output.mkdir(parents=True, exist_ok=True)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    notes_root.mkdir(parents=True, exist_ok=True)
    full_components: list[Path] = []
    actual_components: list[Path] = []
    group_reports = []
    all_tex_paths: list[tuple[str, Path]] = []
    previously_covered_points: dict[str, str] = {}
    for group in groups:
        number, title, display_date, review_flags = _date_number_title(
            group,
            module_root,
            academic_year=academic_year,
        )
        group_label = f"{group['kind'].title()} {number} ({Path(group['relative_dir']).name})"
        print(f"{module}: staging {group_label}", flush=True)
        sources, copy_failures = _stage_group(
            group,
            module_root,
            snapshot_root,
            copy_timeout=45,
        )
        preferences = {stage: preference_context(stage, module=module) for stage in ("draft", "outline")}
        frozen = {"module": module, "slice": "development", "sources": sources}
        blocks = []
        for source in sources:
            blocks.extend(extract_source(source))
        for block in blocks:
            block["relative_path"] = next(source["relative_path"] for source in sources if source["id"] == block["source_id"])
        items, skipped = _draft_group_items(
            frozen,
            blocks,
            endpoint=endpoint,
            model=model,
            visual_model=visual_model,
            checkpoint_dir=checkpoints,
            progress_label=group_label,
        )
        outline_items, repeated_points = separate_repeated_items(
            items, previously_covered_points, group_label
        )
        outline_result = consolidate_items(
            outline_items,
            context=f"{module} — {group_label}",
            module=module,
            endpoint=endpoint,
            model=model,
            checkpoint_dir=checkpoints / "outline",
        )
        if repeated_points:
            reference_bullets = [
                {
                    "text": (
                        f"This content repeats material covered in {previous_group}; see that earlier section. "
                        "No distinct point is added here."
                    ),
                    "support_items": repeated_items,
                    "children": [],
                }
                for previous_group, repeated_items in repeated_points.items()
            ]
            outline_result["sections"].append(
                {"heading": "Previously covered", "bullets": reference_bullets}
            )
            outline_result["stats"]["cross_group_repeated_items"] = sum(
                len(repeated_items) for repeated_items in repeated_points.values()
            )
            outline_result["stats"]["cross_group_references"] = {
                previous_group: len(repeated_items)
                for previous_group, repeated_items in repeated_points.items()
            }
        else:
            outline_result["stats"]["cross_group_repeated_items"] = 0
            outline_result["stats"]["cross_group_references"] = {}
        outline = outline_result["sections"]
        for failure in copy_failures:
            skipped.append(
                {
                    "source_id": f"unavailable:{failure['relative_path']}",
                    "relative_path": failure["relative_path"],
                    "locator": "whole file",
                    "reason": failure["reason"],
                }
            )
        for item in items:
            if item["visual_unreviewed"]:
                review_flags.append(f"Visual content requires human review: {item['relative_path']} {item['locator']}")
                break
        if skipped:
            review_flags.append(f"{len(skipped)} evidence block(s) were not included in drafted note text; see coverage section")
        if outline_result["stats"]["fallback_items"]:
            review_flags.append(
                f"{outline_result['stats']['fallback_items']} point(s) need source-text/organization review; "
                "unassigned points retained under Additional points, ID-only prose restored from the inputs"
            )
        if outline_result["stats"]["cross_group_repeated_items"]:
            review_flags.append(
                f"{outline_result['stats']['cross_group_repeated_items']} exact repeated point(s) cross-referenced to earlier groups"
            )
        note_dir = _group_manifest_path(group, notes_root)
        note_dir.mkdir(parents=True, exist_ok=True)
        body_path = note_dir / "body.tex"
        actual_body_path = note_dir / "body.actual.tex"
        source_by_id = {source["id"]: source for source in sources}
        tutorial_pages = _prepare_tutorial_pages(sources, note_dir)
        reproduced_ids = {page["source_id"] for page in tutorial_pages}
        rendered_items = [item for item in items if item["source_id"] not in reproduced_ids or not item.get("exact_source_text")]
        full_body = _body_fragment(rendered_items, skipped, source_by_id, outline=outline) if rendered_items or skipped else ""
        actual_body = _body_fragment(rendered_items, skipped, source_by_id, include_sources=False, outline=outline) if rendered_items else ""
        body_path.write_text(
            full_body + _tutorial_pages_fragment(tutorial_pages, include_sources=True),
            encoding="utf-8",
            newline="\n",
        )
        actual_body_path.write_text(
            actual_body + _tutorial_pages_fragment(tutorial_pages, include_sources=False),
            encoding="utf-8",
            newline="\n",
        )
        chapter_sources = []
        seen_citations = set()
        for item in items:
            key = (item["relative_path"], item["locator"])
            if key not in seen_citations:
                seen_citations.add(key)
                chapter_sources.append({"path": item["relative_path"], "locator": item["locator"]})
        for item in skipped:
            source = source_by_id.get(item["source_id"])
            if source:
                key = (source["relative_path"], item["locator"])
                if key not in seen_citations:
                    seen_citations.add(key)
                    chapter_sources.append({"path": source["relative_path"], "locator": item["locator"]})
        if not chapter_sources:
            chapter_sources = [{"path": source["relative_path"], "locator": "whole file; no extractable blocks"} for source in sources]
        chapter_sources.extend(
            {"path": failure["relative_path"], "locator": "whole file; source copy failed"}
            for failure in copy_failures
        )
        from .inventory import KIND_LABELS
        chapter = {
            "label": KIND_LABELS.get(group["kind"], "Resource"),
            "number": number,
            "title": title,
            "date": display_date,
            "body_file": "body.tex",
            "sources": chapter_sources,
            "review_flags": review_flags,
        }
        manifest = {
            "module": module,
            "title": f"{module} — {group['kind'].title()} {number}: {title}",
            "academic_year": academic_year,
            "source_files": [
                {"id": source["id"], "role": source["role"], "path": source["relative_path"], "sha256": source["sha256"]}
                for source in sources
            ],
            "assets": [page["asset"] for page in tutorial_pages],
            "tutorial_pages": [{key: value for key, value in page.items() if key != "local_path"} for page in tutorial_pages],
            "lectures": [chapter] if group["kind"] == "lecture" else [],
            "tutorials": [chapter] if group["kind"] == "tutorial" else [],
            "resources": [chapter] if group["kind"] not in {"lecture", "tutorial"} else [],
            "skipped": skipped,
            "processing": {
                "draft_model": model,
                "visual_model": visual_model,
                "endpoint": endpoint,
                "workflow": "module-knowledge.generate-y2",
                "source_copy_timeout_seconds": 45,
                "generation_code_sha256": _file_sha256(Path(__file__)),
                "note_preferences": preferences,
                "draft_prompt_sha256": hashlib.sha256((SYSTEM_PROMPT + preferences["draft"]["prompt_suffix"]).encode("utf-8")).hexdigest(),
                "outline_code_sha256": _file_sha256(Path(__file__).with_name("outline.py")),
                "outline_prompt_sha256": hashlib.sha256((OUTLINE_PROMPT + preferences["outline"]["prompt_suffix"]).encode("utf-8")).hexdigest(),
                "visual_prompt_sha256": hashlib.sha256(VISUAL_PROMPT.encode("utf-8")).hexdigest(),
            },
        }
        manifest_path = note_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        actual_manifest = {
            **manifest,
            "lectures": [{**chapter, "body_file": actual_body_path.name} for chapter in manifest["lectures"]],
            "tutorials": [{**chapter, "body_file": actual_body_path.name} for chapter in manifest["tutorials"]],
            "resources": [{**chapter, "body_file": actual_body_path.name} for chapter in manifest["resources"]],
        }
        actual_manifest_path = note_dir / "manifest.actual.json"
        actual_manifest_path.write_text(
            json.dumps(actual_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        tex_base = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            f"{module}_{group['kind']}_{number}_{Path(group['relative_dir']).name}",
        )
        full_tex_path = note_dir / f"{tex_base}_FULL.tex"
        actual_tex_path = note_dir / f"{tex_base}.tex"
        rendered = render_latex(manifest, full_tex_path, source_root=note_dir, evidence_root=snapshot_root)
        actual_rendered = render_latex(
            actual_manifest,
            actual_tex_path,
            source_root=note_dir,
            evidence_root=snapshot_root,
            include_sources=False,
        )
        full_components.append(full_tex_path)
        actual_components.append(actual_tex_path)
        all_tex_paths.extend([("full", full_tex_path), ("actual", actual_tex_path)])
        group_reports.append(
            {
                "kind": group["kind"],
                "relative_dir": group["relative_dir"],
                "source_count": len(sources),
                "source_copy_failures": copy_failures,
                "evidence_blocks": len(blocks),
                "note_items": len(items),
                "consolidation": outline_result["stats"],
                "weeks": group.get("weeks", []),
                "preserved_tutorial_pages": sum(page["label"].startswith("Tutorial") or page["label"] == "Provided official tutorial solution" for page in tutorial_pages),
                "preserved_source_pages": len(tutorial_pages),
                "provided_solution_pages": sum(page["label"].startswith("Provided official") for page in tutorial_pages),
                "skipped_blocks": len(skipped),
                "review_flags": review_flags,
                "tex": rendered["tex"],
                "actual_tex": actual_rendered["tex"],
                "full_pdf": str(full_tex_path.with_suffix(".pdf")),
                "actual_pdf": str(actual_tex_path.with_suffix(".pdf")),
                "evidence": rendered["evidence"],
                "actual_evidence": actual_rendered["evidence"],
            }
        )
    master_path = module_output / f"{safe_module}_MASTER_FULL.tex"
    actual_master_path = module_output / f"{safe_module}_MASTER.tex"
    master = combine_latex_notes(full_components, master_path, module=module, academic_year=academic_year)
    actual_master = combine_latex_notes(
        actual_components,
        actual_master_path,
        module=module,
        academic_year=academic_year,
        include_sources=False,
    )
    master["pdf"] = str(master_path.with_suffix(".pdf"))
    actual_master["pdf"] = str(actual_master_path.with_suffix(".pdf"))
    all_tex_paths.extend([("full", master_path), ("actual", actual_master_path)])
    compile_reports = []
    if compile_pdfs:
        root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
        for edition, tex_path in all_tex_paths:
            compile_report = _compile_pdf(tex_path, root)
            compile_report["edition"] = edition
            compile_reports.append(compile_report)
            print(f"{module}: compile {edition} {tex_path.name} => {compile_report['status']}", flush=True)
        if all(item["status"] == "ok" for item in compile_reports):
            stale_draft_pdfs = [*notes_root.rglob("*_DRAFT.pdf"), *module_output.glob("*_MASTER_DRAFT.pdf")]
            for stale_pdf in stale_draft_pdfs:
                stale_pdf.unlink(missing_ok=True)
    report = {
        "module": module,
        "format": "latex",
        "source_root": str(module_root),
        "output_root": str(module_output),
        "run_name": run_name,
        "weeks": source_plan.get("weeks") if source_plan else None,
        "input_warnings": source_plan.get("warnings", []) if source_plan else [],
        "groups": group_reports,
        "master": master,
        "actual_master": actual_master,
        "compiled": compile_reports,
        "status": "compiled-draft" if compile_pdfs and all(item["status"] == "ok" for item in compile_reports) else "compile-review-required" if compile_pdfs else "tex-draft-generated",
    }
    if source_plan is not None:
        from .inventory import serialise_plan
        (module_output / "input-inventory.json").write_text(
            json.dumps(serialise_plan(source_plan), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    report_path = module_output / "generation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def generate_y2(
    year_root: Path,
    output_root: Path,
    *,
    academic_year: str,
    endpoint: str = "http://127.0.0.1:11434",
    model: str = "qwen3:8b",
    visual_model: str = "qwen3-vl:8b-instruct",
    compile_pdfs: bool = True,
    project_root: Path | None = None,
    in_module_generated: bool = False,
    modules: list[str] | None = None,
    weeks: list[int] | None = None,
    run_name: str | None = None,
    dry_run: bool = False,
) -> dict:
    from .inventory import plan_module, serialise_plan

    year_root = Path(year_root).resolve(strict=True)
    output_root = Path(output_root).resolve()
    if in_module_generated:
        if output_root != year_root:
            raise ValueError("The output root must equal the Year 2 root with module-generated output")
    elif output_root == year_root or year_root in output_root.parents:
        raise ValueError("Generated notes must be stored outside the Year 2 source tree")
    if (modules or weeks) and not run_name:
        raise ValueError("Scoped generation requires a run name (--run-name) to protect existing outputs")
    if run_name and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_name):
        raise ValueError("Run name must contain only letters, numbers, underscores or hyphens (maximum 80 characters)")
    if weeks is not None and (not weeks or any(type(week) is not int or not 1 <= week <= 53 for week in weeks)):
        raise ValueError("Weeks must be a nonempty list of integers between 1 and 53")
    module_roots = [
        path for path in sorted(year_root.iterdir(), key=lambda candidate: candidate.name.casefold())
        if path.is_dir() and not path.is_symlink()
        and any((path / name).is_dir() for name in ("source", "sources"))
        and (not modules or path.name in modules)
    ]
    missing = set(modules or []) - {path.name for path in module_roots}
    if missing:
        raise ValueError("Unknown module directory: " + ", ".join(sorted(missing)))
    plans = []
    destinations = set()
    for root in module_roots:
        plan = plan_module(root, weeks=weeks)
        if not modules and not plan["files"]:
            continue
        safe_module = re.sub(r"[^A-Za-z0-9_-]+", "-", root.name).strip("-") or "module"
        destination = root / "generated" if in_module_generated else output_root / safe_module
        if run_name:
            destination = destination / "runs" / run_name
        anchor = root if in_module_generated else output_root
        resolved_destination = destination.resolve()
        if destination.is_symlink() or not resolved_destination.is_relative_to(anchor):
            raise ValueError("Output directory must not escape its root through a symlink")
        if resolved_destination in destinations:
            raise ValueError(f"Module output collision: {destination}; select modules separately or use module-local output")
        destinations.add(resolved_destination)
        plan["output_root"] = str(destination)
        plan["run_exists"] = destination.exists() if run_name else False
        plans.append(plan)
    if not plans:
        raise ValueError("No modules with course source folders were found")
    preview = {
        "academic_year": academic_year, "format": "latex", "dry_run": dry_run,
        "run_name": run_name, "weeks": weeks, "module_count": len(plans),
        "modules": [serialise_plan(plan) for plan in plans],
    }
    if dry_run:
        return preview
    # Validate every target before the first snapshot or model request.
    for plan in plans:
        if plan["run_exists"]:
            raise ValueError(f"Named run already exists: {plan['output_root']}; choose a new run name")
        if not plan["selected_count"]:
            raise ValueError(f"No sources selected for {plan['module']}; inspect --dry-run and source-map.json")
    if run_name and any(
        role not in _EXACT_TUTORIAL_ROLES
        for plan in plans for group in plan["groups"] for role in group["source_roles"].values()
    ):
        import urllib.request
        from urllib.parse import urlparse
        address = urlparse(endpoint)
        if address.scheme != "http" or address.hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("Model endpoint must be HTTP on an explicit loopback address")
        try:
            with urllib.request.urlopen(endpoint.rstrip("/") + "/api/tags", timeout=5) as connection:
                available = {entry["name"] for entry in json.load(connection)["models"]}
        except Exception as error:
            raise ValueError(f"Cannot reach the local model service at {endpoint}; start Ollama before generation ({type(error).__name__})") from error
        required = {model, visual_model}
        missing_models = {name for name in required if name not in available and name + ":latest" not in available}
        if missing_models:
            raise ValueError("Missing local model(s): " + ", ".join(sorted(missing_models)))
    reports = [
        generate_module(
            Path(plan["source_root"]), output_root, academic_year=academic_year,
            endpoint=endpoint, model=model, visual_model=visual_model,
            compile_pdfs=compile_pdfs, project_root=project_root,
            in_module_generated=in_module_generated, source_plan=plan, run_name=run_name,
        ) for plan in plans
    ]
    summary = {"academic_year": academic_year, "format": "latex", "run_name": run_name,
               "weeks": weeks, "module_count": len(reports), "modules": reports}
    if not run_name:
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "generation-report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
