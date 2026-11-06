import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from module_knowledge.draft import draft_slice


def test_local_model_drafts_anchored_bullets_without_access_to_gold():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            requests.append(json.loads(self.rfile.read(length)))
            response = json.dumps({"message": {"content": json.dumps({"bullets": ["Sales budget precedes production budget."]})}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        frozen = {"slice": "development", "sources": [{"id": "one", "sha256": "abc", "role": "lecture_handout", "relative_path": "Lecture 2/a.pdf"}]}
        blocks = [{"source_id": "one", "source_sha256": "abc", "relative_path": "Lecture 2/a.pdf", "role": "lecture_handout", "locator": "p.3", "text": "Production units depend on budgeted sales.", "quality_flags": []}]
        draft = draft_slice(frozen, blocks, endpoint=f"http://127.0.0.1:{server.server_port}", model="fake-local")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert draft["items"][0]["text"] == "Sales budget precedes production budget."
    assert draft["items"][0]["source_id"] == "one"
    assert draft["items"][0]["locator"] == "p.3"
    assert draft["items"][0]["fact_checked"] is False
    assert requests[0]["stream"] is False
    assert requests[0]["think"] is False
    assert "Accounting Notes.docx" not in json.dumps(requests)


def test_draft_refuses_remote_endpoint_and_unapproved_gold():
    frozen = {"slice": "development", "sources": []}
    with pytest.raises(ValueError, match="loopback"):
        draft_slice(frozen, [], endpoint="https://api.example.com", model="m")
    frozen["sources"].append({"id": "gold", "sha256": "abc", "role": "student_style_gold", "relative_path": "Accounting Notes.docx"})
    with pytest.raises(ValueError, match="gold"):
        draft_slice(frozen, [], endpoint="http://127.0.0.1:11434", model="m")


def test_visual_only_solution_is_skipped_not_invented():
    frozen = {"slice": "development", "sources": [{"id": "answer", "sha256": "abc", "role": "tutorial_solution", "relative_path": "02j.pdf"}]}
    blocks = [{"source_id": "answer", "source_sha256": "abc", "relative_path": "02j.pdf", "role": "tutorial_solution", "locator": "p.2", "text": "Question with visually marked answer", "quality_flags": ["needs_visual_answer_review"]}]
    draft = draft_slice(frozen, blocks, endpoint="http://127.0.0.1:11434", model="m")
    assert draft["items"] == []
    assert draft["skipped"][0]["reason"] == "needs_visual_answer_review"


def test_unreviewed_visual_table_is_not_drafted_from_flattened_text():
    frozen = {"slice": "development", "sources": [{"id": "handout", "sha256": "abc", "role": "lecture_handout", "relative_path": "Lecture 2/handout.pdf"}]}
    blocks = [{"source_id": "handout", "source_sha256": "abc", "relative_path": "Lecture 2/handout.pdf", "role": "lecture_handout", "locator": "p.1", "text": "Bear Dog Rabbit Total £'000 Sales 5,500 7,600", "quality_flags": ["needs_visual_review"]}]

    draft = draft_slice(frozen, blocks, endpoint="http://127.0.0.1:11434", model="m")

    assert draft["items"] == []
    assert draft["skipped"][0]["reason"] == "needs_visual_review"


def test_oversized_model_output_is_recorded_as_gap_not_silently_truncated():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            response = json.dumps({"message": {"content": json.dumps({"bullets": ["Same idea"] * 31})}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        frozen = {"slice": "development", "sources": [{"id": "s", "sha256": "x", "role": "lecture_slides", "relative_path": "s.pptx"}]}
        blocks = [{"source_id": "s", "source_sha256": "x", "relative_path": "s.pptx", "role": "lecture_slides", "locator": "slide 1", "text": "Budgeting concept", "quality_flags": []}]
        result = draft_slice(frozen, blocks, endpoint=f"http://127.0.0.1:{server.server_port}", model="fake")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    assert result["items"] == []
    assert result["skipped"][0]["reason"] == "invalid_model_output"


def test_visual_model_transcription_is_always_marked_unreviewed(tmp_path):
    frozen = {"slice": "development", "sources": [{"id": "s", "sha256": "x", "role": "lecture_handout", "relative_path": "handout.pdf"}]}
    blocks = [{"source_id": "s", "source_sha256": "x", "relative_path": "handout.pdf", "role": "lecture_handout", "locator": "p.2", "text": "Visually transcribed table", "quality_flags": ["visual_model_unverified"]}]
    cached = tmp_path / "cache"
    # A real local response is exercised in the other drafting test; use the same behavior here.
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            response = json.dumps({"message": {"content": json.dumps({"bullets": ["Visually transcribed table"]})}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = draft_slice(frozen, blocks, endpoint=f"http://127.0.0.1:{server.server_port}", model="fake", checkpoint_dir=cached)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    assert result["items"][0]["visual_unreviewed"] is True
