"""Regression probes from independent scoped-generation review."""
import json
from pathlib import Path

import pytest

from module_knowledge.generation import generate_y2
from module_knowledge.inventory import plan_module


def _question(root, module="ML", text="Question 1: Define overfitting."):
    path = root / module / "source/mock-tests/Week 1/mock.txt"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


def test_external_output_symlink_ancestor_rejected_before_writes(tmp_path):
    source, output, outside = (tmp_path / name for name in ("source-root", "output", "outside"))
    _question(source)
    output.mkdir()
    outside.mkdir()
    (output / "ML").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        generate_y2(source, output, academic_year="2026--27", modules=["ML"], weeks=[1], run_name="safe", compile_pdfs=False)
    assert list(outside.iterdir()) == []


def test_normalised_module_destinations_rejected_before_writes(tmp_path):
    source, output = tmp_path / "source-root", tmp_path / "output"
    for name in ("A B", "A-B"):
        _question(source, name)
    with pytest.raises(ValueError, match="output collision"):
        generate_y2(source, output, academic_year="2026--27", weeks=[1], run_name="safe", compile_pdfs=False)
    assert not output.exists()


def test_exact_question_path_references_survive_both_editions_and_master(tmp_path):
    text = "Question 1: Open source/data.csv and report its first row.\nQuestion 2: Define overfitting."
    _question(tmp_path, text=text)
    report = generate_y2(tmp_path, tmp_path, academic_year="2026--27", modules=["ML"], weeks=[1], run_name="safe", in_module_generated=True, compile_pdfs=False)
    module = report["modules"][0]
    for result in (module["groups"][0], {"tex": module["master"]["tex"], "actual_tex": module["actual_master"]["tex"]}):
        for key in ("tex", "actual_tex"):
            output = Path(result[key]).read_text()
            assert "Question 1: Open source/data.csv and report its first row." in output
            assert "Question 2: Define overfitting." in output


def test_legacy_multiple_lectures_keep_their_numbers_within_one_week(tmp_path):
    for number in (1, 2):
        path = tmp_path / f"source/lectures/Week 1/lecture{number}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    plan = plan_module(tmp_path, weeks=[1])
    assert [group["number"] for group in plan["groups"]] == ["1", "2"]
    assert all(group["weeks"] == [1] for group in plan["groups"])


@pytest.mark.parametrize("label,expected", [("Week 1 and Week 6", [1, 6]), ("Weeks 1 and 6", [1, 6]), ("Week 1, Week 6", [1, 6]), ("Weeks 1-3 and 6", [1, 2, 3, 6]), ("Weeks 1-3, and 6", [1, 2, 3, 6]), ("Weeks 1, 3, and 6", [1, 3, 6])])
def test_all_explicit_week_labels_contribute_to_scope(tmp_path, label, expected):
    path = tmp_path / "source/mock-tests" / label / "mock.txt"
    path.parent.mkdir(parents=True)
    path.write_text("fixture")
    entry = plan_module(tmp_path, weeks=[1, 2, 3])["files"][0]
    assert entry["weeks"] == expected
    assert entry["status"] == "partial-week-overlap"
