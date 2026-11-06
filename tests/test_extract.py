from pathlib import Path
import json

import pymupdf
from docx import Document
from docx.shared import Inches as DocxInches
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from module_knowledge.extract import extract_frozen, extract_source


def test_pdf_extraction_is_page_anchored_and_flags_visual_gaps(tmp_path):
    pdf = pymupdf.open()
    first = pdf.new_page()
    first.insert_text((72, 72), "Revenue equals price times quantity. The units are pounds per sale.")
    second = pdf.new_page()
    second.draw_rect(pymupdf.Rect(72, 72, 300, 300), color=(0, 0, 0))
    path = tmp_path / "handout.pdf"
    pdf.save(path)
    source = {"id": "official-handout", "sha256": "abc", "role": "lecture_handout", "local_path": str(path)}

    blocks = extract_source(source)

    assert [x["locator"] for x in blocks] == ["p.1", "p.2"]
    assert "Revenue equals price times quantity" in blocks[0]["text"]
    assert blocks[0]["source_id"] == "official-handout"
    assert blocks[0]["source_sha256"] == "abc"
    assert "needs_ocr" in blocks[1]["quality_flags"]
    assert "needs_visual_review" in blocks[1]["quality_flags"]
    assert blocks[1]["text"] == ""


def test_pptx_extraction_keeps_slide_and_speaker_notes(tmp_path):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(7), Inches(1))
    box.text = "Cash budgets allocate receipts and payments"
    image = tmp_path / "figure.png"
    Image.new("RGB", (20, 20), "blue").save(image)
    slide.shapes.add_picture(str(image), Inches(1), Inches(2))
    notes = slide.notes_slide.notes_text_frame
    assert notes is not None
    notes.text = "Explain the month-end cash balance"
    path = tmp_path / "lecture.pptx"
    deck.save(path)

    blocks = extract_source({"id": "lecture", "sha256": "def", "role": "lecture_slides", "local_path": str(path)})

    assert [x["locator"] for x in blocks] == ["slide 1"]
    assert "Cash budgets" in blocks[0]["text"]
    assert "month-end cash balance" in blocks[0]["text"]
    assert "needs_visual_review" in blocks[0]["quality_flags"]


def test_pptx_numeric_table_flattened_as_text_needs_visual_review(tmp_path):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(7), Inches(3)).text = "Bear Dog Rabbit Total £'000\nSales 5,500 7,600 14,400 27,500\nMaterials 1,600 1,280 1,920 4,800"
    path = tmp_path / "numeric-table.pptx"
    deck.save(path)

    blocks = extract_source({"id": "deck", "sha256": "abc", "role": "lecture_slides", "local_path": str(path)})

    assert "needs_visual_review" in blocks[0]["quality_flags"]


def test_docx_extraction_keeps_paragraph_and_table_provenance(tmp_path):
    document = Document()
    document.add_heading("Budgeting", level=1)
    document.add_paragraph("Sales budget comes before a production budget")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Sales"
    table.cell(0, 1).text = "100"
    image = tmp_path / "chart.png"
    Image.new("RGB", (30, 30), "red").save(image)
    document.add_picture(str(image), width=DocxInches(1))
    path = tmp_path / "official.docx"
    document.save(path)

    blocks = extract_source({"id": "official", "sha256": "xyz", "role": "tutorial_question", "local_path": str(path)})

    assert "Budgeting" in blocks[0]["text"]
    assert "production budget" in blocks[1]["text"]
    assert any("Sales | 100" in b["text"] and b["locator"].startswith("table ") for b in blocks)
    assert any("needs_visual_review" in b["quality_flags"] for b in blocks)


def test_extract_frozen_writes_jsonl_with_quality_report(tmp_path):
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "A revenue budget estimates the expected value of sales.")
    source_file = tmp_path / "source.pdf"
    pdf.save(source_file)
    frozen = {"slice": "development", "sources": [{"id": "one", "sha256": "abc", "role": "lecture_handout", "relative_path": "Lecture 2/source.pdf", "local_path": str(source_file)}]}
    output = tmp_path / "private" / "evidence.jsonl"

    report = extract_frozen(frozen, output)

    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert report["blocks"] == 1
    assert report["source_count"] == 1
    assert rows[0]["relative_path"] == "Lecture 2/source.pdf"
    assert rows[0]["locator"] == "p.1"


def test_same_extracted_question_and_answer_text_flags_visual_answer_gap(tmp_path):
    files = []
    for label in ("question", "answer"):
        pdf = pymupdf.open()
        pdf.new_page().insert_text((72, 72), "Which budget comes before production? Sales budget is an option.")
        pdf.set_metadata({"title": label})
        path = tmp_path / f"{label}.pdf"
        pdf.save(path)
        files.append({"id": label, "sha256": label, "role": "tutorial_solution" if label == "answer" else "tutorial_question", "relative_path": path.name, "local_path": str(path)})
    out = tmp_path / "evidence.jsonl"

    report = extract_frozen({"slice": "development", "sources": files}, out)

    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert "needs_visual_answer_review" in rows[1]["quality_flags"]
    assert report["flags"]["needs_visual_answer_review"] == 1
