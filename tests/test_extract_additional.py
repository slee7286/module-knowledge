from pathlib import Path

from module_knowledge.extract import extract_source


def test_extract_text_and_python_sources_in_bounded_line_chunks(tmp_path: Path):
    text_source = tmp_path / "captions.txt"
    text_source.write_text("line one\nline two\n", encoding="utf-8")
    python_source = tmp_path / "cheatsheet.py"
    python_source.write_text("print('example')\n", encoding="utf-8")
    sources = [
        {"id": "txt", "sha256": "a", "role": "lecture_transcript", "local_path": str(text_source)},
        {"id": "py", "sha256": "b", "role": "tutorial_code", "local_path": str(python_source)},
    ]

    transcript = extract_source(sources[0])
    code = extract_source(sources[1])

    assert transcript[0]["locator"] == "lines 1--2"
    assert transcript[0]["text"] == "line one\nline two"
    assert code[0]["locator"] == "lines 1--1"
    assert code[0]["text"] == "print('example')"
    assert code[0]["method"] == "python-source"
