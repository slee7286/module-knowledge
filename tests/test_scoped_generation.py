import json
from pathlib import Path

import pytest

from module_knowledge.generation import discover_source_groups


def test_inventory_discovers_new_roles_and_accounts_for_every_source(tmp_path):
    from module_knowledge.inventory import plan_module

    module = tmp_path / "Machine Learning"
    names = {
        "lecture-slides/Week 1/lecture1.pdf": "lecture_slides",
        "lecture-transcripts/Week 1/transcript.txt": "lecture_transcript",
        "problem-sets/Week 1/PS1.pdf": "tutorial_question",
        "problem-set-solutions/Week 1/PS1.pdf": "tutorial_solution",
        "tutorial-slides/Week 1/tutorial.pdf": "tutorial_handout",
        "miscellaneous/Week 1/mentimeter.pdf": "supplementary_material",
        "mock-tests/Week 1-5/mock.pdf": "mock_question",
        "mock-test-solutions/Week 1-5/mock.pdf": "mock_solution",
        "midterm-study-guides/Week 1-5/guide.pdf": "study_guide",
    }
    for relative in [*names, "lecture-slides/Week 6/lecture6.pdf", "miscellaneous/unknown.pdf", "miscellaneous/Week 1/video.mp4", "readings/Week 1/book.pdf"]:
        path = module / "source" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    plan = plan_module(module, weeks=[1, 2, 3, 4, 5])
    selected = {entry["path"].removeprefix("source/"): entry["role"] for entry in plan["files"] if entry["status"] == "selected"}
    assert selected == names
    assert len(plan["files"]) == 13
    assert {entry["status"] for entry in plan["files"]} == {"selected", "outside-week-scope", "unassigned-week", "unsupported-format", "excluded-category"}
    lectures = [group for group in plan["groups"] if group["kind"] == "lecture"]
    assert len(lectures) == 1
    assert len(lectures[0]["files"]) == 2
    assert plan["warnings"]
    assert not (module / "generated").exists()


def test_week_scope_requires_explicit_labels_or_mapping_and_rejects_partial_overlap(tmp_path):
    from module_knowledge.inventory import plan_module

    module = tmp_path / "Machine Learning"
    folder = module / "source/lectures/2026-10-05_01"
    folder.mkdir(parents=True)
    (folder / "lecture1.pdf").write_text("fixture")
    mock = module / "source/mock-tests/Week 1-6/mock.pdf"
    mock.parent.mkdir(parents=True)
    mock.write_text("fixture")
    assert plan_module(module, weeks=[1, 2, 3, 4, 5])["selected_count"] == 0
    (module / "source-map.json").write_text(json.dumps({"sources": {"source/lectures/2026-10-05_01": {"weeks": [1], "date": "2026-10-05"}}}))
    plan = plan_module(module, weeks=[1, 2, 3, 4, 5])
    assert plan["selected_count"] == 1
    assert next(entry for entry in plan["files"] if entry["path"].endswith("mock.pdf"))["status"] == "partial-week-overlap"
    assert plan["groups"][0]["date"] == "2026-10-05"


def test_cli_preview_is_read_only_and_scoped_to_exact_module(tmp_path, capsys, monkeypatch):
    from module_knowledge.cli import main
    import module_knowledge.generation as generation

    for module in ("Machine Learning", "Other Module"):
        path = tmp_path / module / "source/lecture-slides/Week 1/slides.pdf"
        path.parent.mkdir(parents=True)
        path.write_text("fixture")
    monkeypatch.setattr(generation, "generate_module", lambda *_a, **_k: pytest.fail("Preview must not generate"))
    before = sorted(str(path) for path in tmp_path.rglob("*"))
    assert main(["generate-y2", "--year-root", str(tmp_path), "--output-root", str(tmp_path), "--in-module-generated", "--academic-year", "2026--27", "--module", "Machine Learning", "--weeks", "1-5", "--run-name", "weeks-1-5", "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["module_count"] == 1
    assert report["modules"][0]["module"] == "Machine Learning"
    assert report["modules"][0]["selected_count"] == 1
    assert report["modules"][0]["output_root"] == str(tmp_path / "Machine Learning/generated/runs/weeks-1-5")
    assert before == sorted(str(path) for path in tmp_path.rglob("*"))


def test_scoped_generation_requires_a_fresh_named_run_before_any_write(tmp_path):
    from module_knowledge.generation import generate_y2

    path = tmp_path / "Machine Learning/source/problem-sets/Week 1/PS1.pdf"
    path.parent.mkdir(parents=True)
    path.write_text("fixture")
    existing = tmp_path / "Machine Learning/generated/runs/first/keep.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep")
    with pytest.raises(ValueError, match="run name"):
        generate_y2(tmp_path, tmp_path, academic_year="2026--27", modules=["Machine Learning"], weeks=[1], in_module_generated=True)
    with pytest.raises(ValueError, match="already exists"):
        generate_y2(tmp_path, tmp_path, academic_year="2026--27", modules=["Machine Learning"], weeks=[1], run_name="first", in_module_generated=True)
    assert existing.read_text() == "keep"
    assert not (tmp_path / "generation-report.json").exists()


def test_named_run_preserves_mock_questions_and_official_solutions_without_models(tmp_path, monkeypatch):
    import pymupdf
    import module_knowledge.generation as generation

    module = tmp_path / "Machine Learning"
    for category, text in (("mock-tests", "Question 1: define overfitting."), ("mock-test-solutions", "Official answer: poor generalisation.")):
        path = module / "source" / category / "Week 1-5/mock.pdf"
        path.parent.mkdir(parents=True)
        with pymupdf.open() as document:
            document.new_page().insert_text((50, 50), text)
            document.new_page()  # Image-only/blank pages must survive without OCR.
            document.save(path)
    monkeypatch.setattr(generation, "draft_slice", lambda *_a, **_k: pytest.fail("Do not generate exam answers"))
    monkeypatch.setattr(generation, "recover_pdf_page", lambda *_a, **_k: pytest.fail("Original pages need no OCR"))
    report = generation.generate_y2(tmp_path, tmp_path, academic_year="2026--27", modules=["Machine Learning"], weeks=[1, 2, 3, 4, 5], run_name="fixture", in_module_generated=True, compile_pdfs=False)
    result = report["modules"][0]
    assert result["output_root"] == str(module / "generated/runs/fixture")
    assert len(result["groups"]) == 2
    assert sum(group["preserved_source_pages"] for group in result["groups"]) == 4
    for group, heading in zip(result["groups"], ("Mock test", "Mock test solution")):
        text = Path(group["tex"]).read_text()
        assert heading in text
        assert r"\section{Tutorial" not in text
        assert text.count(r"\includegraphics") == 2
        clean = Path(group["actual_tex"]).read_text().split(r"\pagenumbering{arabic}")[1]
        assert "source/mock" not in clean
    assert result["groups"][1]["provided_solution_pages"] == 2
    inventory = json.loads((module / "generated/runs/fixture/input-inventory.json").read_text())
    assert inventory["selected_count"] == 2
    assert not (tmp_path / "generation-report.json").exists()


def test_resource_manifest_uses_explicit_resource_heading(tmp_path):
    from module_knowledge.latex import render_latex

    (tmp_path / "body.tex").write_text("Revision checklist.")
    output = tmp_path / "resource.tex"
    render_latex({"module": "Machine Learning", "resources": [{"number": "1-5", "label": "Midterm study guide", "title": "Weeks 1-5", "date": "Date not supplied", "body_file": "body.tex"}]}, output, source_root=tmp_path)
    assert r"\section{Midterm study guide 1-5: Weeks 1-5 (Date not supplied)}" in output.read_text()


def test_week_zero_source_is_reported_out_of_scope_instead_of_breaking_preview(tmp_path):
    from module_knowledge.inventory import plan_module

    path = tmp_path / "source/tutorials/2026-10-08_01/EFDS_ML_Week 0_ps0.pdf"
    path.parent.mkdir(parents=True)
    path.write_text("fixture")
    plan = plan_module(tmp_path, weeks=[1, 2, 3, 4, 5])
    assert plan["files"][0]["weeks"] == [0]
    assert plan["files"][0]["status"] == "outside-week-scope"


def test_unfiltered_inventory_keeps_legacy_group_intact_with_week_zero_and_unlabelled_files(tmp_path):
    from module_knowledge.inventory import plan_module

    folder = tmp_path / "source/tutorials/2026-10-08_01"
    folder.mkdir(parents=True)
    for name in ("EFDS_ML_Week 0_ps0.pdf", "cheatsheet.py"):
        (folder / name).write_text("fixture")
    plan = plan_module(tmp_path)
    assert len(plan["groups"]) == 1
    assert len(plan["groups"][0]["files"]) == 2


def test_mapped_date_is_used_in_preview_and_missing_dates_are_reported(tmp_path):
    from module_knowledge.inventory import plan_module

    folder = tmp_path / "source/lectures/Week 1"
    folder.mkdir(parents=True)
    (folder / "lecture1.pdf").write_text("fixture")
    assert any("date" in warning.lower() for warning in plan_module(tmp_path, weeks=[1])["warnings"])
    (tmp_path / "source-map.json").write_text(json.dumps({"sources": {"source/lectures/Week 1": {"weeks": [1], "date": "2026-10-05"}}}))
    plan = plan_module(tmp_path, weeks=[1])
    assert not any("No explicit date" in warning for warning in plan["warnings"])


def test_colliding_component_destinations_fail_in_preview(tmp_path):
    from module_knowledge.inventory import plan_module

    for root in ("source", "sources"):
        path = tmp_path / root / "lectures/Week 1/lecture1.pdf"
        path.parent.mkdir(parents=True)
        path.write_text("fixture")
    with pytest.raises(ValueError, match="output collision"):
        plan_module(tmp_path, weeks=[1])


def test_convenience_script_defaults_to_preview_without_creating_outputs(tmp_path):
    import os
    import subprocess

    path = tmp_path / "Machine Learning/source/problem-sets/Week 1/PS1.pdf"
    path.parent.mkdir(parents=True)
    path.write_text("fixture")
    script = Path(__file__).resolve().parents[1] / "scripts/machine-learning-weeks-1-5.sh"
    result = subprocess.run(["sh", str(script)], env={**os.environ, "ONEDRIVE_ROOT": str(tmp_path)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert not (tmp_path / "Machine Learning/generated").exists()


def test_missing_local_model_service_fails_before_reserving_named_run(tmp_path, monkeypatch):
    import urllib.error
    import module_knowledge.generation as generation

    path = tmp_path / "Machine Learning/source/lecture-slides/Week 1/lecture1.pdf"
    path.parent.mkdir(parents=True)
    path.write_text("fixture")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: (_ for _ in ()).throw(urllib.error.URLError("fixture offline")))
    with pytest.raises(ValueError, match="local model service"):
        generation.generate_y2(tmp_path, tmp_path, academic_year="2026--27", modules=["Machine Learning"], weeks=[1], run_name="first", in_module_generated=True, compile_pdfs=False)
    assert not (tmp_path / "Machine Learning/generated").exists()


def test_inventory_keeps_excluded_nested_notes_out_of_model_inputs(tmp_path):
    from module_knowledge.inventory import plan_module

    path = tmp_path / "source/lectures/Week 1/notes/gold.txt"
    path.parent.mkdir(parents=True)
    path.write_text("held-out fixture")
    plan = plan_module(tmp_path, weeks=[1])
    assert plan["selected_count"] == 0
    assert plan["files"][0]["status"] == "excluded-category"


@pytest.mark.parametrize("metadata", [{"weeks": [0]}, {"weeks": [True]}, {"weeks": "1-5"}, {"weeks": [1], "date": "2026-02-30"}])
def test_invalid_source_metadata_fails_before_generation(tmp_path, metadata):
    from module_knowledge.inventory import plan_module

    module = tmp_path / "Machine Learning"
    module.mkdir()
    (module / "source-map.json").write_text(json.dumps({"sources": {"source/lectures/Week 1": metadata}}))
    with pytest.raises(ValueError):
        plan_module(module, weeks=[1])
