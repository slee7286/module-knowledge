import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from module_knowledge.draft import draft_slice
from module_knowledge.outline import _request_outline
from module_knowledge.preferences import preference_context


@pytest.mark.parametrize("scope", ["all", "Machine Learning"])
def test_saved_preferences_reach_draft_and_outline_requests(tmp_path, monkeypatch, scope):
    preferences = tmp_path / "preferences.json"
    preferences.write_text(json.dumps({"version": 1, "rules": [{
        "id": "reasoning", "status": "active", "scope": scope,
        "stages": ["draft", "outline"],
        "instruction": "Make intermediate algebra steps explicit.",
        "feedback_ids": ["review-1"],
    }]}))
    monkeypatch.setenv("MODULE_KNOWLEDGE_PREFERENCES", str(preferences))
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            content = {"bullets": ["A supported step."], "sections": []}
            response = json.dumps({"message": {"content": json.dumps(content)}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    try:
        frozen = {"module": "Machine Learning", "slice": "development", "sources": [{
            "id": "s", "sha256": "abc", "role": "lecture_slides", "relative_path": "slide.pdf",
        }]}
        blocks = [{"source_id": "s", "source_sha256": "abc", "relative_path": "slide.pdf",
                   "role": "lecture_slides", "locator": "p.1", "text": "A supported step.", "quality_flags": []}]
        draft_slice(frozen, blocks, endpoint=endpoint, model="test-local", checkpoint_dir=tmp_path / "draft")
        _request_outline([{"id": "u000001", "text": "A supported step."}],
                         context="Machine Learning", endpoint=endpoint, model="test-local",
                         checkpoint_dir=tmp_path / "outline",
                         **({"module": scope} if scope != "all" else {}))
        updated = json.loads(preferences.read_text())
        updated["rules"][0]["instruction"] = "Make intermediate algebra steps explicit, with units."
        preferences.write_text(json.dumps(updated))
        draft_slice(frozen, blocks, endpoint=endpoint, model="test-local", checkpoint_dir=tmp_path / "draft")
        _request_outline([{"id": "u000001", "text": "A supported step."}],
                         context="Machine Learning", endpoint=endpoint, model="test-local",
                         checkpoint_dir=tmp_path / "outline",
                         **({"module": scope} if scope != "all" else {}))
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    assert len(requests) == 4
    for request in requests[:2]:
        assert "Make intermediate algebra steps explicit." in request["messages"][0]["content"]
    for request in requests[2:]:
        assert "Make intermediate algebra steps explicit, with units." in request["messages"][0]["content"]
    assert len(list((tmp_path / "draft").glob("*.json"))) == 2
    assert len(list((tmp_path / "outline").glob("*.json"))) == 2
    assert "Never infer a solution" in requests[0]["messages"][0]["content"]
    assert "Do not infer beyond" in requests[1]["messages"][0]["content"]


def test_generation_records_the_preferences_used(tmp_path, monkeypatch):
    import hashlib

    import pymupdf

    from module_knowledge.draft import SYSTEM_PROMPT
    from module_knowledge.generation import generate_module

    preferences = tmp_path / "preferences.json"
    preferences.write_text(json.dumps({"version": 1, "rules": [{
        "id": "style", "status": "active", "scope": "all", "stages": ["draft", "outline"],
        "instruction": "Retain intermediate reasoning.", "feedback_ids": ["review-2"],
    }]}))
    monkeypatch.setenv("MODULE_KNOWLEDGE_PREFERENCES", str(preferences))
    module = tmp_path / "Machine Learning"
    source = module / "source/tutorials/2026-10-08_01/Week 1 Tutorial.pdf"
    source.parent.mkdir(parents=True)
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50, 50), "Exercise: explain the calculation.")
        doc.save(source)
    generate_module(module, tmp_path, academic_year="2026--27",
                    in_module_generated=True, compile_pdfs=False)
    manifest_path = next((module / "generated").rglob("manifest.json"))
    processing = json.loads(manifest_path.read_text())["processing"]
    saved = processing["note_preferences"]
    assert saved["draft"]["rules"][0]["id"] == "style"
    assert saved["outline"]["sha256"]
    effective = SYSTEM_PROMPT + saved["draft"]["prompt_suffix"]
    assert processing["draft_prompt_sha256"] == hashlib.sha256(effective.encode()).hexdigest()


def test_malformed_preference_stages_fail_instead_of_silently_applying(tmp_path, monkeypatch):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"version": 1, "rules": [{
        "id": "bad", "status": "active", "scope": "all", "stages": "draft",
        "instruction": "Do not silently accept malformed rules.", "feedback_ids": [],
    }]}))
    monkeypatch.setenv("MODULE_KNOWLEDGE_PREFERENCES", str(path))
    with pytest.raises(ValueError, match="stages"):
        preference_context("draft")


def test_only_active_scoped_presentation_rules_are_used(tmp_path, monkeypatch):
    path = tmp_path / "preferences.json"
    baseline = {"status": "active", "scope": "all", "stages": ["draft", "outline"],
                "instruction": "Keep reasoning.", "feedback_ids": []}
    rules = [dict(baseline, id="global"),
             dict(baseline, id="candidate", status="candidate"),
             dict(baseline, id="old", status="superseded"),
             dict(baseline, id="different-module", scope="Econometrics 1"),
             dict(baseline, id="review", stages=["review"]),
             dict(baseline, id="matching-module", scope="Machine Learning")]
    path.write_text(json.dumps({"version": 1, "rules": rules}))
    monkeypatch.setenv("MODULE_KNOWLEDGE_PREFERENCES", str(path))
    selected = preference_context("draft", module="Machine Learning")
    assert [rule["id"] for rule in selected["rules"]] == ["global", "matching-module"]
    assert [rule["id"] for rule in preference_context("draft")["rules"]] == ["global"]


def test_explicit_missing_register_does_not_silently_forget_preferences(tmp_path, monkeypatch):
    monkeypatch.setenv("MODULE_KNOWLEDGE_PREFERENCES", str(tmp_path / "missing.json"))
    with pytest.raises(FileNotFoundError):
        preference_context("draft")


def test_reviewed_style_rules_are_loaded_for_future_generation(monkeypatch):
    monkeypatch.delenv("MODULE_KNOWLEDGE_PREFERENCES", raising=False)
    expected = {"study-first-clean-edition", "principle-over-incidental-illustration",
                "figures-before-dependent-explanation", "explicit-example-classifications",
                "question-then-worked-answer"}
    for stage in ("draft", "outline", "review"):
        selected = preference_context(stage, module="Machine Learning")
        indexed = {rule["id"]: rule for rule in selected["rules"]}
        assert expected <= indexed.keys()
        for id in expected:
            assert indexed[id]["instruction"] in selected["prompt_suffix"]
            assert indexed[id]["feedback_ids"]
