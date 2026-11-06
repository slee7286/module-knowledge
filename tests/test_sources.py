import hashlib
import json
from pathlib import Path

import pytest

from module_knowledge.sources import freeze_slice


def test_freeze_development_copies_only_selected_official_source(tmp_path):
    root = tmp_path / "OneDrive" / "Accounting"
    root.mkdir(parents=True)
    (root / "02a handout.pdf").write_bytes(b"%PDF-example-source")
    (root / "Accounting Notes.docx").write_bytes(b"GOLD MUST STAY PRIVATE")
    manifest = {
        "module": "Accounting",
        "slices": {
            "development": {"sources": [{"path": "02a handout.pdf", "role": "lecture_handout"}]},
            "locked_test": {"sources": [{"path": "Accounting Notes.docx", "role": "test"}]},
        },
    }
    config = tmp_path / "pilot.json"
    config.write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "private"

    result = freeze_slice(config, root, out, "development")

    assert result["slice"] == "development"
    assert len(result["sources"]) == 1
    row = result["sources"][0]
    assert row["sha256"] == hashlib.sha256(b"%PDF-example-source").hexdigest()
    assert Path(row["local_path"]).read_bytes() == b"%PDF-example-source"
    assert "Accounting Notes" not in json.dumps(result)
    assert b"GOLD MUST STAY PRIVATE" not in b"".join(p.read_bytes() for p in (out / "sources").iterdir())


def test_freeze_rejects_gold_and_path_escape(tmp_path):
    root = tmp_path / "Accounting"
    root.mkdir()
    (root / "Accounting Notes.docx").write_bytes(b"GOLD")
    for forbidden in ["Accounting Notes.docx", "../outside.pdf"]:
        config = tmp_path / "pilot.json"
        config.write_text(json.dumps({"slices": {"development": {"sources": [{"path": forbidden, "role": "lecture"}]}}}))
        with pytest.raises(ValueError):
            freeze_slice(config, root, tmp_path / "private", "development")


def test_locked_test_requires_explicit_unlock(tmp_path):
    root = tmp_path / "Accounting"
    root.mkdir()
    (root / "slide.pdf").write_bytes(b"%PDF-test")
    config = tmp_path / "pilot.json"
    config.write_text(json.dumps({"slices": {"locked_test": {"sources": [{"path": "slide.pdf", "role": "lecture"}]}}}))
    with pytest.raises(PermissionError):
        freeze_slice(config, root, tmp_path / "private", "locked_test")
