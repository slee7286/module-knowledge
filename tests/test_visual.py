import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pymupdf

from module_knowledge.visual import recover_pdf_page


def test_local_visual_recovery_anchors_output_and_never_marks_verified(tmp_path):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(request)
            response = json.dumps({"message": {"content": json.dumps({"transcription": "| Sales | £'000 |\n| Bear | 5,500 |", "unreadable": []})}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Sales £'000 Bear 5,500")
    path = tmp_path / "handout.pdf"
    document.save(path)
    source = {"id": "handout", "sha256": "abc", "role": "lecture_handout", "relative_path": "Lecture 2/handout.pdf", "local_path": str(path)}
    block = {"source_id": "handout", "source_sha256": "abc", "relative_path": source["relative_path"], "role": source["role"], "locator": "p.1", "text": "flattened table", "quality_flags": ["needs_visual_review"]}
    try:
        recovered = recover_pdf_page(source, block, endpoint=f"http://127.0.0.1:{server.server_port}", model="fake-vl")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert received[0]["messages"][1]["images"]
    assert "Bear | 5,500" in recovered["text"]
    assert recovered["locator"] == "p.1"
    assert recovered["source_sha256"] == "abc"
    assert recovered["quality_flags"] == ["visual_model_unverified"]
