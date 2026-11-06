import json

from docx import Document

from module_knowledge.evaluate import evaluate_candidate, extract_gold_sections


def test_gold_extraction_is_section_isolated(tmp_path):
    gold = Document()
    gold.add_heading("Lecture 1: CVP", level=1)
    gold.add_paragraph("LOCKED TEST BODY")
    gold.add_heading("Tutorial 1", level=1)
    gold.add_paragraph("LOCKED TEST SOLUTION")
    gold.add_heading("Lecture 2: Budgeting", level=1)
    gold.add_paragraph("Budgeting lesson in short bullets", style="List Paragraph")
    gold.add_heading("Tutorial 2", level=1)
    gold.add_paragraph("Worked tutorial method")
    gold.add_heading("Lecture 3", level=1)
    gold.add_paragraph("FUTURE BODY")
    path = tmp_path / "Accounting Notes.docx"
    gold.save(path)

    extracted = extract_gold_sections(path, label="Lecture 2 + Tutorial 2")

    assert [p["text"] for p in extracted["paragraphs"]] == ["Lecture 2: Budgeting", "Budgeting lesson in short bullets", "Tutorial 2", "Worked tutorial method"]
    assert extracted["metrics"]["list_paragraphs"] == 1
    assert "LOCKED" not in json.dumps(extracted)


def test_candidate_evaluation_checks_locator_not_truth_and_never_passes_unreviewed(tmp_path):
    path = tmp_path / "draft.tex"
    path.write_text(
        r"\section{Lecture 2}" + "\n" + r"\begin{itemize}" + "\n" + r"\item Budgeting lesson in short bullets" + "\n" + r"\end{itemize}" + "\n",
        encoding="utf-8",
    )
    sidecar = {"items": [{"item_id": "i1", "source_id": "one", "locator": "p.99", "relative_path": "Lecture 2/a.pdf", "fact_checked": False, "visual_unreviewed": True}], "skipped": [], "unreviewed_visual_items": 1}
    evidence = [{"source_id": "one", "locator": "p.2", "text": "Official source facts", "quality_flags": [], "role": "lecture_handout"}]
    gold = {"paragraphs": [{"text": "Budgeting lesson in short bullets", "style": "List Paragraph"}], "metrics": {"list_paragraphs": 1}}

    report = evaluate_candidate(gold, path, sidecar, evidence)

    assert report["citation_integrity"]["invalid_locator_count"] == 1
    assert report["content_coverage_status"] == "ungraded_requires_human_review"
    assert report["fact_checked_items"] == 0
    assert report["gate"] == "not_passed"
