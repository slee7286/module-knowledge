"""Deterministic, source-aware LaTeX rendering for module notes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unicodedata


_TEMPLATE = Path(__file__).parent / "templates" / "module-notes.tex"
_PLACEHOLDERS = ("%%TITLE%%", "%%MODULE%%", "%%DATE%%", "%%EDITION%%", "%%BODY%%")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _escape_tex(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = "".join(
        unicodedata.normalize("NFKC", character)
        if unicodedata.name(character, "").startswith("MATHEMATICAL ")
        else character
        for character in text
    )
    text = text.replace("β̂", "\x00HATBETA\x00").replace("ε̂", "\x00HATEPSILON\x00")
    hat_tokens: dict[str, str] = {}

    def protect_hat(match: re.Match[str]) -> str:
        symbol = match.group(1)
        symbol_tex = {
            "α": r"\alpha",
            "β": r"\beta",
            "γ": r"\gamma",
            "δ": r"\delta",
            "ε": r"\epsilon",
            "ϵ": r"\varepsilon",
            "η": r"\eta",
            "θ": r"\theta",
            "λ": r"\lambda",
            "μ": r"\mu",
            "µ": r"\mu",
            "π": r"\pi",
            "σ": r"\sigma",
            "φ": r"\phi",
            "ϕ": r"\varphi",
            "ω": r"\omega",
        }.get(symbol, symbol)
        token = f"\x00HAT{len(hat_tokens)}\x00"
        hat_tokens[token] = rf"$\hat{{{symbol_tex}}}$"
        return token

    text = re.sub(r"ˆ([A-Za-zα-ωΑ-Ωµϵϕ])", protect_hat, text)
    relation_tokens: dict[str, str] = {}

    def protect_not_equal(match: re.Match[str]) -> str:
        token = f"\x00REL{len(relation_tokens)}\x00"
        relation_tokens[token] = r" $\neq$ "
        return token

    text = re.sub(r"̸\s*=\s*", protect_not_equal, text)
    tilde_tokens: dict[str, str] = {}

    def protect_tilde(match: re.Match[str]) -> str:
        token = f"\x00TILDE{len(tilde_tokens)}\x00"
        tilde_tokens[token] = rf"$\tilde{{{match.group(1)}}}$"
        return token

    text = re.sub(r"([A-Za-z])̃", protect_tilde, text)
    text = text.replace("困境", "[unrendered CJK text]")
    exponent_tokens: dict[str, str] = {}

    def protect_negative_exponent(match: re.Match[str]) -> str:
        token = f"\x00EXP{len(exponent_tokens)}\x00"
        digits = match.group(1).translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
        exponent_tokens[token] = rf"\textsuperscript{{-{digits}}}"
        return token

    text = re.sub(r"⁻([0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+)", protect_negative_exponent, text)
    escaped = "".join(
        {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
        }.get(character, character)
        for character in text
    )
    replacements = {
        "\x00HATBETA\x00": r"$\hat{\beta}$",
        "\x00HATEPSILON\x00": r"$\hat{\epsilon}$",
        "α": r"$\alpha$",
        "β": r"$\beta$",
        "ε": r"$\epsilon$",
        "ϵ": r"$\varepsilon$",
        "θ": r"$\theta$",
        "λ": r"$\lambda$",
        "μ": r"$\mu$",
        "π": r"$\pi$",
        "σ": r"$\sigma$",
        "Σ": r"$\Sigma$",
        "τ": r"$\tau$",
        "φ": r"$\phi$",
        "ϕ": r"$\varphi$",
        "ω": r"$\omega$",
        "γ": r"$\gamma$",
        "δ": r"$\delta$",
        "η": r"$\eta$",
        "µ": r"$\mu$",
        "ŷ": r"$\hat{y}$",
        "≤": r"$\leq$",
        "≥": r"$\geq$",
        "≃": r"$\simeq$",
        "≡": r"$\equiv$",
        "≠": r"$\neq$",
        "≈": r"$\approx$",
        "⇒": r"$\Rightarrow$",
        "⇐": r"$\Leftarrow$",
        "∗": r"$\ast$",
        "×": r"$\times$",
        "·": r"$\cdot$",
        "∈": r"$\in$",
        "∼": r"$\sim$",
        "˜": r"$\sim$",
        "∑": r"$\sum$",
        "∫": r"$\int$",
        "∩": r"$\cap$",
        "⊂": r"$\subset$",
        "↑": r"$\uparrow$",
        "∃": r"$\exists$",
        "∆": r"$\Delta$",
        "∴": r"$\therefore$",
        "√": r"$\surd$",
        "½": r"$\frac{1}{2}$",
        "ℓ": r"$\ell$",
        "✓": r"$\checkmark$",
        "✗": r"$\times$",
        "…": "...",
        "ₜ": r"$_{t}$",
        "ᵗ": r"\textsuperscript{t}",
        "₤": "[unrendered currency symbol]",
        "\uf8eb": "(",
        "\uf8ec": "(",
        "\uf8ed": "(",
        "\uf8f6": ")",
        "\uf8f7": ")",
        "\uf8f8": ")",
        "ˆ": r"\textasciicircum{}",
        "′": "'",
        "⁻": r"\textsuperscript{-}",
        "¹": r"\textsuperscript{1}",
        "∞": r"$\infty$",
        "→": r"$\to$",
        "ᵢ": r"$_{i}$",
        "₀": r"$_{0}$",
        "₁": r"$_{1}$",
        "₂": r"$_{2}$",
        "³": r"$^{3}$",
        "⁴": r"$^{4}$",
        "²": r"$^{2}$",
        "−": "--",
        "–": "--",
        "—": "---",
        "‘": "``",
        "’": "''",
        "“": "``",
        "”": "''",
        "•": r"\textbullet{}",
    }
    for character, replacement in replacements.items():
        escaped = escaped.replace(character, replacement)
    for token, replacement in hat_tokens.items():
        escaped = escaped.replace(token, replacement)
    for token, replacement in exponent_tokens.items():
        escaped = escaped.replace(token, replacement)
    for token, replacement in relation_tokens.items():
        escaped = escaped.replace(token, replacement)
    for token, replacement in tilde_tokens.items():
        escaped = escaped.replace(token, replacement)
    return escaped


def _tex_group_end(text: str, start: int) -> int | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    index = start
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _strip_tex_macro(text: str, name: str, argument_count: int) -> str:
    pattern = re.compile(rf"\\{re.escape(name)}\b")
    while match := pattern.search(text):
        end = match.end()
        for _ in range(argument_count):
            while end < len(text) and text[end].isspace():
                end += 1
            end = _tex_group_end(text, end)
            if end is None:
                raise ValueError(f"Malformed {name} command in citation-free note body")
        text = text[: match.start()] + text[end:]
    return text


def _strip_source_citations(text: str) -> str:
    return _strip_tex_macro(text, "sourcecite", 2)


def _strip_review_flags(text: str) -> str:
    return _strip_tex_macro(text, "reviewflag", 1)


def _strip_literal_source_path_lines(text: str) -> str:
    """Remove typed provenance lines, never pedagogical paths or exact source blocks."""
    lines = []
    exact = False
    metadata = re.compile(r"(?i)^\s*(?:\\item\s+)?(?:data source|source locator|source path|source file|sources?)\s*:")
    for line in text.splitlines():
        if line == "% BEGIN EXACT SOURCE":
            exact = True
        if exact or not (metadata.search(line) and re.search(r"(?i)(?:source|sources)/", line)):
            lines.append(line)
        if line == "% END EXACT SOURCE":
            exact = False
    return "\n".join(lines)


def _load_template(template_path: Path | None) -> tuple[str, Path]:
    path = Path(template_path) if template_path is not None else _TEMPLATE
    template = path.read_text(encoding="utf-8")
    expected_counts = {"%%MODULE%%": 2}
    for placeholder in _PLACEHOLDERS:
        expected = expected_counts.get(placeholder, 1)
        if template.count(placeholder) != expected:
            raise ValueError(f"LaTeX template must contain exactly {expected} {placeholder} placeholders")
    return template, path


def _source_entries(chapters: dict[str, list[dict]]) -> list[dict]:
    entries = []
    for chapter_type, items in chapters.items():
        for chapter in items:
            for source in chapter.get("sources", []):
                if not isinstance(source, dict) or not source.get("path") or not source.get("locator"):
                    raise ValueError("Each source citation needs a path and exact locator")
                entries.append({chapter_type: chapter["number"], **source})
    return entries


def _structured_body(
    draft: dict,
    root: Path,
    evidence_root: Path,
    *,
    include_sources: bool,
) -> tuple[str, list[dict], list[dict]]:
    chapters = {kind: draft.get(kind, []) for kind in ("lectures", "tutorials", "resources")}
    if not any(isinstance(items, list) and items for items in chapters.values()):
        raise ValueError("A LaTeX note manifest needs at least one lecture, tutorial or resource")
    body_parts = []
    inputs = []
    assets = []
    for chapter_type, items in chapters.items():
        label = chapter_type[:-1].title()
        for chapter in items:
            label = str(chapter.get("label") or "Resource") if chapter_type == "resources" else chapter_type[:-1].title()
            number = str(chapter.get("number", "")).strip()
            title = str(chapter.get("title", "")).strip()
            date = str(chapter.get("date", "")).strip()
            fragment = str(chapter.get("body_file", "")).strip()
            if not number or not title or not date or not fragment:
                raise ValueError(f"Each {label.lower()} needs an explicit number, title, date, and body_file")
            relative = Path(fragment)
            if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".tex":
                raise ValueError(f"{label} body_file must be a relative .tex path inside the manifest root")
            path = (root / relative).resolve(strict=True)
            if not path.is_file() or not path.is_relative_to(root):
                raise ValueError(f"{label} body_file resolves outside the manifest root")
            text = path.read_text(encoding="utf-8")
            if not include_sources:
                text = _strip_source_citations(text)
                text = _strip_review_flags(text)
                text = _strip_literal_source_path_lines(text)
            if r"\documentclass" in text or r"\end{document}" in text:
                raise ValueError(f"{label} body fragments must not contain a document wrapper")
            heading = rf"\section{{{label} {_escape_tex(number)}: {_escape_tex(title)} ({_escape_tex(date)})}}"
            safe_number = re.sub(r"[^A-Za-z0-9:-]", "-", number)
            body_parts.extend([heading, rf"\label{{{label.lower()}:{safe_number}}}"])
            review_flags = chapter.get("review_flags", []) if include_sources else []
            if review_flags:
                body_parts.extend(
                    [
                        r"\begin{itemize}",
                        *(rf"\item \reviewflag{{{_escape_tex(flag)}}}" for flag in review_flags),
                        r"\end{itemize}",
                    ]
                )
            body_parts.append(text.rstrip())
            inputs.append({"kind": "body_fragment", "path": relative.as_posix(), "sha256": _sha256(path)})
    for source in draft.get("source_files", []):
        if not isinstance(source, dict) or not source.get("path"):
            raise ValueError("Each source_files entry needs a relative path")
        relative = Path(str(source["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Source files must be relative to the evidence root")
        path = (evidence_root / relative).resolve(strict=True)
        if not path.is_file() or not path.is_relative_to(evidence_root):
            raise ValueError("Source file resolves outside the evidence root")
        actual_hash = _sha256(path)
        expected_hash = source.get("sha256")
        if expected_hash and str(expected_hash).lower() != actual_hash:
            raise ValueError(f"Source SHA-256 mismatch for {relative.as_posix()}")
        inputs.append(
            {
                "kind": "source_file",
                "path": relative.as_posix(),
                "sha256": actual_hash,
                "id": source.get("id"),
                "role": source.get("role"),
            }
        )
    for asset in draft.get("assets", []):
        relative = Path(str(asset))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("LaTeX assets must be relative to the manifest root")
        path = (root / relative).resolve(strict=True)
        if not path.is_file() or not path.is_relative_to(root):
            raise ValueError("LaTeX asset resolves outside the manifest root")
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".pdf"}:
            raise ValueError(f"Unsupported LaTeX figure type: {path.suffix}")
        assets.append({"kind": "figure_asset", "path": relative.as_posix(), "sha256": _sha256(path)})
    return "\n\n".join(body_parts), inputs, assets


def _flat_body(draft: dict, label: str, *, include_sources: bool) -> tuple[str, list[dict]]:
    if draft.get("slice") not in {"development", "locked_test"}:
        raise ValueError("A frozen pilot slice is required")
    chapters = [part.strip() for part in label.split(" + ") if part.strip()]
    parts = []
    evidence = []
    current_chapter = None
    current_source = None
    list_open = False

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            parts.append(r"\end{itemize}")
            list_open = False

    for item in draft.get("items", []):
        if not item.get("text") or not item.get("source_id") or not item.get("locator"):
            raise ValueError("Every LaTeX note item needs text and a source locator")
        role = str(item.get("role", "other")).casefold()
        chapter_kind = "lecture" if role.startswith("lecture") else "tutorial" if role.startswith("tutorial") else "other"
        if chapter_kind != current_chapter:
            close_list()
            current_chapter = chapter_kind
            current_source = None
            heading = next((part for part in chapters if part.casefold().startswith(chapter_kind)), chapter_kind.title())
            parts.append(rf"\section{{{_escape_tex(heading)}}}")
        relative_path = str(item.get("relative_path", "source"))
        if relative_path != current_source:
            close_list()
            current_source = relative_path
            heading = _escape_tex(Path(relative_path).stem) if include_sources else "Notes"
            parts.append(rf"\subsection{{{heading}}}")
            parts.append(r"\begin{itemize}")
            list_open = True
        review = (
            r" \reviewflag{visual review pending}"
            if include_sources and item.get("visual_unreviewed")
            else ""
        )
        citation = (
            rf" \sourcecite{{{_escape_tex(relative_path)}}}{{{_escape_tex(item['locator'])}}}"
            if include_sources
            else ""
        )
        item_text = item["text"].strip()
        if not include_sources:
            item_text = _strip_literal_source_path_lines(item_text).strip()
        if not item_text:
            continue
        parts.append(rf"\item {_escape_tex(item_text)}{citation}{review}")
        evidence.append(
            {
                "item_id": item.get("id"),
                "source_id": item["source_id"],
                "relative_path": relative_path,
                "locator": item["locator"],
                "fact_checked": bool(item.get("fact_checked", False)),
                "visual_unreviewed": bool(item.get("visual_unreviewed", False)),
            }
        )
    close_list()
    skipped = draft.get("skipped", []) if include_sources else []
    if skipped:
        parts.extend([r"\section*{Extraction and review gaps}", r"\begin{itemize}"])
        for item in skipped:
            descriptor = f"{item.get('source_id', 'source')}, {item.get('locator', 'unknown locator')}: {item.get('reason', 'review required')}"
            parts.append(rf"\item {_escape_tex(descriptor)}")
        parts.append(r"\end{itemize}")
    return "\n".join(parts), evidence


def _guard_output_paths(
    destination: Path,
    sidecar_path: Path,
    root: Path,
    evidence_root: Path,
    inputs: list[dict],
    assets: list[dict],
) -> None:
    output_paths = {destination.resolve(), sidecar_path.resolve()}
    for item in inputs:
        base = evidence_root if item.get("kind") == "source_file" else root
        input_path = (base / item["path"]).resolve(strict=True)
        if input_path in output_paths:
            raise ValueError(f"Output would overwrite a manifest input: {item['path']}")
    for asset in assets:
        asset_path = (root / asset["path"]).resolve(strict=True)
        if asset_path in output_paths:
            raise ValueError(f"Output would overwrite a LaTeX asset: {asset['path']}")


def render_latex(
    draft: dict,
    output_path: Path,
    *,
    label: str | None = None,
    source_root: Path | None = None,
    evidence_root: Path | None = None,
    template_path: Path | None = None,
    include_sources: bool = True,
) -> dict:
    """Render either a structured LaTeX manifest or the pipeline's flat draft JSON."""
    destination = Path(output_path)
    if destination.suffix.lower() != ".tex":
        raise ValueError("LaTeX renderer output must use the .tex extension")
    if not draft.get("module"):
        raise ValueError("A module name is required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = Path(source_root or destination.parent).resolve(strict=True)
    evidence_base = Path(evidence_root or root).resolve(strict=True)
    template, template_file = _load_template(template_path)
    if any(kind in draft for kind in ("lectures", "tutorials", "resources")):
        body, inputs, assets = _structured_body(
            draft, root, evidence_base, include_sources=include_sources
        )
        evidence = _source_entries({kind: draft.get(kind, []) for kind in ("lectures", "tutorials", "resources")})
        title = draft.get("title") or f"{draft['module']} Notes"
        date = draft.get("academic_year") or draft.get("date") or ""
        skipped = draft.get("skipped", [])
        draft_items = sum(
            1
            for kind in ("lectures", "tutorials", "resources")
            for chapter in draft.get(kind, [])
            for _ in chapter.get("sources", [])
        )
    else:
        render_label = label or "Lecture 1"
        body, evidence = _flat_body(draft, render_label, include_sources=include_sources)
        inputs = []
        assets = []
        title = draft.get("title") or f"{draft['module']} Notes"
        date = draft.get("academic_year") or ""
        skipped = draft.get("skipped", [])
        draft_items = len(evidence)
    substitutions = {
        "%%TITLE%%": _escape_tex(title),
        "%%MODULE%%": _escape_tex(draft["module"]),
        "%%DATE%%": _escape_tex(date),
        "%%EDITION%%": (
            "FULL VERSION: source citations and review information included"
            if include_sources
            else "CITATION-FREE STUDY NOTES: content not independently fact-checked"
        ),
        "%%BODY%%": body,
    }
    tex = template
    for placeholder, value in substitutions.items():
        tex = tex.replace(placeholder, value)
    sidecar_path = destination.with_suffix(".evidence.json")
    _guard_output_paths(destination, sidecar_path, root, evidence_base, inputs, assets)
    destination.write_text(tex, encoding="utf-8", newline="\n")
    sidecar = {
        "format": "latex",
        "module": draft["module"],
        "title": title,
        "slice": draft.get("slice"),
        "model": draft.get("model"),
        "template": str(template_file),
        "template_sha256": _sha256(template_file),
        "inputs": inputs,
        "assets": assets,
        "sources": evidence,
        "processing": draft.get("processing", {}),
        "items": evidence if "items" in draft else [],
        "skipped": skipped,
        "output_sha256": _sha256(destination),
    }
    sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "format": "latex",
        "tex": str(destination),
        "evidence": str(sidecar_path),
        "draft_items": draft_items,
        "skipped": len(skipped),
        "input_files": len(inputs) + len(assets),
    }


def combine_latex_notes(
    component_paths: list[Path],
    output_path: Path,
    *,
    module: str,
    academic_year: str,
    template_path: Path | None = None,
    include_sources: bool = True,
) -> dict:
    """Combine standalone lecture/tutorial notes into one master LaTeX document."""
    destination = Path(output_path)
    if destination.suffix.lower() != ".tex":
        raise ValueError("Master LaTeX output must use the .tex extension")
    if not module or not component_paths:
        raise ValueError("Master notes require a module name and at least one component")
    template, template_file = _load_template(template_path)
    body_parts = []
    components = []
    sources = []
    for component in component_paths:
        path = Path(component).resolve(strict=True)
        if path == destination.resolve():
            raise ValueError("Master output cannot overwrite a component note")
        sidecar_path = path.with_suffix(".evidence.json")
        if not sidecar_path.is_file():
            raise ValueError(f"Component provenance sidecar is missing: {path.name}")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if sidecar.get("format") != "latex" or sidecar.get("module") != module:
            raise ValueError(f"Component note is not a LaTeX note for {module}: {path.name}")
        tex = path.read_text(encoding="utf-8")
        match = re.search(
            r"\\clearpage\s*\\pagenumbering\{arabic\}\s*(.*?)\\end\{document\}\s*$",
            tex,
            flags=re.DOTALL,
        )
        if match is None:
            raise ValueError(f"Component note does not use the supported module-notes template: {path.name}")
        body = match.group(1).strip()
        if not body:
            raise ValueError(f"Component note has an empty body: {path.name}")
        if not include_sources:
            body = _strip_source_citations(body)
            body = _strip_review_flags(body)
            body = _strip_literal_source_path_lines(body)
        body_parts.append(body)
        components.append({"path": str(path), "sha256": _sha256(path), "evidence": str(sidecar_path)})
        sources.extend(sidecar.get("sources", []))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sidecar_destination = destination.with_suffix(".evidence.json")
    occupied = {Path(item["path"]).resolve() for item in components}
    occupied.update(Path(item["evidence"]).resolve() for item in components)
    if destination.resolve() in occupied or sidecar_destination.resolve() in occupied:
        raise ValueError("Master output would overwrite a component note or provenance sidecar")
    title = f"{module} — Master Notes"
    tex = template
    for placeholder, value in {
        "%%TITLE%%": _escape_tex(title),
        "%%MODULE%%": _escape_tex(module),
        "%%DATE%%": _escape_tex(academic_year),
        "%%EDITION%%": (
            "FULL VERSION: source citations and review information included"
            if include_sources
            else "CITATION-FREE STUDY NOTES: content not independently fact-checked"
        ),
        "%%BODY%%": "\n\n".join(body_parts),
    }.items():
        tex = tex.replace(placeholder, value)
    destination.write_text(tex, encoding="utf-8", newline="\n")
    sidecar = {
        "format": "latex",
        "module": module,
        "title": title,
        "academic_year": academic_year,
        "template": str(template_file),
        "template_sha256": _sha256(template_file),
        "components": components,
        "sources": sources,
        "output_sha256": _sha256(destination),
    }
    sidecar_destination.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "format": "latex",
        "tex": str(destination),
        "evidence": str(sidecar_destination),
        "component_count": len(components),
        "source_citations": len(sources),
    }
