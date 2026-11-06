"""Read-only source inventory and explicit week scoping for course-note runs."""
from __future__ import annotations

from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re


# Directory names are normalised for spaces/underscores, never source paths.
CATEGORIES = {
    "lectures": ("lecture", None),
    "lecture-slides": ("lecture", "lecture_slides"),
    "lecture-transcripts": ("lecture", "lecture_transcript"),
    "tutorials": ("tutorial", None),
    "tutorial-slides": ("tutorial", "tutorial_handout"),
    "problem-sets": ("problem-set", "tutorial_question"),
    "problem-set-solutions": ("problem-set-solution", "tutorial_solution"),
    "miscellaneous": ("miscellaneous", "supplementary_material"),
    "mock-tests": ("mock-test", "mock_question"),
    "mock-test-solutions": ("mock-test-solution", "mock_solution"),
    "midterm-study-guides": ("study-guide", "study_guide"),
}
KIND_LABELS = {
    "lecture": "Lecture", "tutorial": "Tutorial", "problem-set": "Problem set",
    "problem-set-solution": "Problem set solution", "miscellaneous": "Supplementary material",
    "mock-test": "Mock test", "mock-test-solution": "Mock test solution", "study-guide": "Midterm study guide",
}
_WEEK = re.compile(r"(?i)(?<![a-z0-9])weeks?[\s_-]*(\d+)(?:\s*[-–]\s*(\d+))?(?!\d)")


def parse_weeks(value: str) -> list[int]:
    if not re.fullmatch(r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*", value):
        raise ValueError("Weeks must be positive numbers/ranges, for example 1-5 or 1,3-5")
    result = set()
    for part in value.split(","):
        bounds = [int(item) for item in part.split("-")]
        start, end = bounds[0], bounds[-1]
        if start < 1 or end < start or end > 53:
            raise ValueError("Weeks must be ascending ranges between 1 and 53")
        result.update(range(start, end + 1))
    return sorted(result)


def _metadata(root: Path) -> dict:
    path = root / "source-map.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sources"), dict):
        raise ValueError("source-map.json must contain a sources object")
    for key, entry in data["sources"].items():
        relative = Path(key)
        if not relative.parts or relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in {"source", "sources"}:
            raise ValueError("Source-map keys must be paths under source/ or sources/")
        if not isinstance(entry, dict) or set(entry) - {"weeks", "date"}:
            raise ValueError(f"Invalid source-map entry: {key}; allowed fields are weeks and date")
        weeks = entry.get("weeks")
        if not isinstance(weeks, list) or not weeks or any(type(week) is not int or not 1 <= week <= 53 for week in weeks):
            raise ValueError(f"Source-map weeks must be a nonempty list of integers between 1 and 53: {key}")
        if "date" in entry:
            try:
                date.fromisoformat(entry["date"])
            except (ValueError, TypeError):
                raise ValueError(f"Source-map date must be a valid ISO date: {key}") from None
    return data["sources"]


def _scope(relative: str, mapping: dict) -> tuple[list[int], str | None]:
    matches = [key for key in mapping if relative == key or relative.startswith(key.rstrip("/") + "/")]
    if matches:
        entry = mapping[max(matches, key=len)]
        return sorted(set(entry["weeks"])), entry.get("date")
    # Collect every explicitly labelled scope, including lists such as
    # "Weeks 1-3 and 6". A child label cannot silently erase a parent week.
    assigned = set()
    expression = re.compile(
        r"(?i)(?<![a-z0-9])weeks?[\s_-]*(\d+(?:\s*[-–]\s*\d+)?"
        r"(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)(?:weeks?\s*)?\d+(?:\s*[-–]\s*\d+)?)*)"
    )
    for part in Path(relative).parts:
        for match in expression.finditer(part):
            for token in re.finditer(r"(\d+)(?:\s*[-–]\s*(\d+))?", match[1]):
                start, end = int(token[1]), int(token[2] or token[1])
                if not 0 <= start <= end <= 53:
                    raise ValueError(f"Invalid week label in source path: {relative}")
                assigned.update(range(start, end + 1))
    return sorted(assigned), None


def plan_module(module_root: Path, *, weeks: list[int] | None = None) -> dict:
    from .generation import _date_number_title, _group_manifest_path, _source_role, _SUPPORTED_SUFFIXES, _IGNORED_DIRS, discover_source_groups

    root = Path(module_root).resolve(strict=True)
    mapping = _metadata(root)
    legacy = {path: group for group in discover_source_groups(root) for path in group["files"]}
    selected_weeks = set(weeks or [])
    files = []
    groups = {}
    warnings = []
    for source_name in ("source", "sources"):
        source_root = root / source_name
        if not source_root.is_dir() or source_root.is_symlink():
            continue
        for base, directories, names in os.walk(source_root, followlinks=False):
            directory = Path(base)
            directories[:] = sorted(name for name in directories if not (directory / name).is_symlink())
            for name in sorted(names):
                path = directory / name
                relative = path.relative_to(root).as_posix()
                parts = Path(relative).parts
                category = parts[1].casefold().replace("_", "-").replace(" ", "-") if len(parts) > 2 else ""
                kind, explicit_role = CATEGORIES.get(category, (None, None))
                assigned_weeks, teaching_date = _scope(relative, mapping)
                role = explicit_role or (_source_role(kind, path) if kind else None)
                if path.is_symlink():
                    status = "excluded-symlink"
                elif kind is None or any(part.casefold() in _IGNORED_DIRS for part in parts[2:-1]):
                    status = "excluded-category"
                elif path.suffix.casefold() not in _SUPPORTED_SUFFIXES:
                    status = "unsupported-format"
                elif selected_weeks and not assigned_weeks:
                    status = "unassigned-week"
                elif selected_weeks and not selected_weeks.intersection(assigned_weeks):
                    status = "outside-week-scope"
                elif selected_weeks and not set(assigned_weeks).issubset(selected_weeks):
                    status = "partial-week-overlap"
                else:
                    status = "selected"
                files.append({"path": relative, "role": role, "weeks": assigned_weeks, "date": teaching_date, "status": status})
                if status != "selected":
                    continue
                original = legacy.get(path)
                if original:
                    event = original["relative_dir"]
                    number = original["number"]
                    flags = list(original.get("review_flags", []))
                else:
                    event = Path(*parts[:3]).as_posix() if len(parts) > 3 else Path(*parts[:2]).as_posix()
                    number = str(assigned_weeks[0]) if assigned_weeks else "?"
                    flags = []
                    if kind == "lecture" and assigned_weeks:
                        event = f"{source_name}/lectures/Week {'-'.join(map(str, (assigned_weeks[0], assigned_weeks[-1])))}"
                if not original and assigned_weeks and _WEEK.search(Path(event).name):
                    number = str(assigned_weeks[0])
                key = (kind, event, number)
                group = groups.setdefault(key, {"kind": kind, "relative_dir": event, "number": number, "weeks": assigned_weeks, "files": [], "source_roles": {}, "review_flags": flags})
                group["files"].append(path)
                group["weeks"] = sorted(set(group["weeks"]) | set(assigned_weeks))
                group["source_roles"][relative] = role
                if teaching_date:
                    previous = group.get("date")
                    if previous and previous != teaching_date:
                        raise ValueError(f"Conflicting mapped dates in source group {event}")
                    group["date"] = teaching_date
    destinations = set()
    for group in groups.values():
        destination = _group_manifest_path(group, Path("notes"))
        if destination in destinations:
            raise ValueError(f"Component output collision: {destination}; use distinct event directory names")
        destinations.add(destination)
        _, _, _, date_flags = _date_number_title(group, root)
        warnings.extend(f"{group['relative_dir']}: {flag}" for flag in date_flags)
    for week in weeks or []:
        roles = {entry["role"] for entry in files if entry["status"] == "selected" and week in entry["weeks"]}
        for role in ("lecture_slides", "lecture_transcript", "tutorial_question", "tutorial_solution", "tutorial_handout"):
            if role not in roles:
                warnings.append(f"Week {week}: no selected {role.replace('_', ' ')} source")
    for entry in files:
        if entry["status"] in {"unassigned-week", "partial-week-overlap", "unsupported-format"}:
            warnings.append(f"{entry['path']}: {entry['status']}")
    counts = dict(sorted(Counter(entry["status"] for entry in files).items()))
    order = {kind: index for index, kind in enumerate(KIND_LABELS)}
    group_list = sorted(groups.values(), key=lambda group: (order[group["kind"]], group["weeks"], group["relative_dir"], group["number"]))
    return {"module": root.name, "source_root": str(root), "weeks": weeks, "files": files, "file_counts": counts, "selected_count": counts.get("selected", 0), "warnings": warnings, "groups": group_list}


def serialise_plan(plan: dict) -> dict:
    return {**plan, "groups": [{**group, "files": [str(path) for path in group["files"]]} for group in plan["groups"]]}
