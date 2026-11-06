"""Load reviewed note-writing preferences independently of conversation state."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "note-preferences.json"


def preference_context(stage: str, *, module: str | None = None) -> dict:
    configured = os.environ.get("MODULE_KNOWLEDGE_PREFERENCES")
    path = Path(configured).expanduser() if configured else DEFAULT_PATH
    if not path.exists() and not configured:
        data = {"version": 1, "rules": []}
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("rules"), list):
        raise ValueError("Invalid note preference register")
    rules = []
    for rule in data["rules"]:
        if not isinstance(rule, dict):
            raise ValueError("Invalid note preference rule")
        stages = rule.get("stages")
        if not isinstance(stages, list) or any(value not in {"draft", "outline", "review"} for value in stages):
            raise ValueError("Invalid note preference stages")
        if rule.get("status") != "active" or stage not in stages:
            continue
        if rule.get("scope") not in ("all", module):
            continue
        if not isinstance(rule.get("instruction"), str) or not rule["instruction"].strip():
            raise ValueError("Active note preference needs an instruction")
        rules.append(rule)
    encoded = json.dumps(rules, ensure_ascii=False, sort_keys=True).encode("utf-8")
    text = ""
    if rules:
        text = ("\n\nApproved note preferences (presentation only; preserve the evidence, "
                "coverage, academic-integrity and output-schema requirements above):\n"
                + "\n".join("- " + rule["instruction"] for rule in rules))
    return {"path": str(path.resolve()), "rules": rules,
            "sha256": hashlib.sha256(encoded).hexdigest(), "prompt_suffix": text}
