import json
from pathlib import Path

import pymupdf

from module_knowledge.generation import _body_fragment, _date_number_title, _gvfs_source_uri, _source_role, _stage_group, discover_source_groups
from module_knowledge.latex import combine_latex_notes
from module_knowledge.render import render_latex


def test_discovery_includes_lecture_and_tutorial_sources_but_not_readings_or_video(tmp_path):
    module = tmp_path / "Machine Learning"
    lecture = module / "source" / "lectures" / "2026-10-05_01"
    tutorial = module / "source" / "tutorials" / "2026-10-08_01"
    reading = module / "source" / "readings"
    for directory in (lecture, tutorial, reading):
        directory.mkdir(parents=True)
    (lecture / "lecture1.pdf").write_bytes(b"lecture pdf")
    (lecture / "captions.txt").write_text("lecture transcript", encoding="utf-8")
    (lecture / "lecture.mp4").write_bytes(b"video")
    (tutorial / "PS1.pdf").write_bytes(b"problem set")
    (tutorial / "answers.docx").write_bytes(b"handout")
    (reading / "textbook.pdf").write_bytes(b"reading")

    groups = discover_source_groups(module)

    assert [(group["kind"], group["relative_dir"]) for group in groups] == [
        ("lecture", "source/lectures/2026-10-05_01"),
        ("tutorial", "source/tutorials/2026-10-08_01"),
    ]
    assert [path.name for path in groups[0]["files"]] == ["captions.txt", "lecture1.pdf"]
    assert [path.name for path in groups[1]["files"]] == ["answers.docx", "PS1.pdf"]


def test_master_latex_combines_standalone_lecture_and_tutorial_without_nested_front_matter(tmp_path):
    components = []
    for kind, number, text in (("lecture", 1, "Lecture finding."), ("tutorial", 1, "Official answer.")):
        body = tmp_path / f"{kind}.body.tex"
        body.write_text(r"\subsection{Material}" + "\n" + text, encoding="utf-8")
        source = tmp_path / f"{kind}.pdf"
        source.write_bytes(f"source {kind}".encode())
        manifest = {
            "module": "Microeconomics 2",
            "lectures": [] if kind == "tutorial" else [{
                "number": number, "title": "Consumer choice", "date": "5 October 2026",
                "body_file": body.name, "sources": [{"path": source.name, "locator": "PDF p. 1"}],
            }],
            "tutorials": [] if kind == "lecture" else [{
                "number": number, "title": "Problem set 1", "date": "8 October 2026",
                "body_file": body.name, "sources": [{"path": source.name, "locator": "PDF p. 2"}],
            }],
            "source_files": [{"path": source.name}],
        }
        output = tmp_path / f"{kind}.tex"
        render_latex(manifest, output, source_root=tmp_path)
        components.append(output)

    master = tmp_path / "Microeconomics-2-Master.tex"
    report = combine_latex_notes(components, master, module="Microeconomics 2", academic_year="2026--27")

    tex = master.read_text(encoding="utf-8")
    assert tex.count(r"\documentclass") == 1
    assert tex.count(r"\tableofcontents") == 1
    assert r"\section{Lecture 1: Consumer choice (5 October 2026)}" in tex
    assert r"\section{Tutorial 1: Problem set 1 (8 October 2026)}" in tex
    assert "Lecture finding." in tex and "Official answer." in tex
    assert report["component_count"] == 2
    sidecar = json.loads(master.with_suffix(".evidence.json").read_text(encoding="utf-8"))
    assert len(sidecar["components"]) == 2
    assert {entry["locator"] for entry in sidecar["sources"]} == {"PDF p. 1", "PDF p. 2"}


def test_discovery_splits_multiple_lecture_and_problem_set_outputs(tmp_path):
    module = tmp_path / "Corporate Finance and Capital Markets"
    lectures = module / "sources" / "lectures" / "2026-10-06_01"
    tutorials = module / "sources" / "tutorials" / "2026-10-08_01"
    lectures.mkdir(parents=True)
    tutorials.mkdir(parents=True)
    for name in ("Week 0 Lecture 0.pdf", "Week 1 Lecture 1.pdf", "Lecture captions.txt"):
        (lectures / name).write_text(name, encoding="utf-8")
    for name in ("EFDS_ML_Week 0_ps0.pdf", "PS1.pdf", "cheatsheet.py"):
        (tutorials / name).write_text(name, encoding="utf-8")

    groups = discover_source_groups(module)

    assert [(group["kind"], group["number"]) for group in groups] == [
        ("lecture", "0"),
        ("lecture", "1"),
        ("tutorial", "0"),
        ("tutorial", "1"),
    ]
    assert [path.name for path in groups[0]["files"]] == ["Week 0 Lecture 0.pdf"]
    assert {path.name for path in groups[1]["files"]} == {"Week 1 Lecture 1.pdf", "Lecture captions.txt"}
    assert {path.name for path in groups[2]["files"]} == {"cheatsheet.py", "EFDS_ML_Week 0_ps0.pdf"}
    assert [path.name for path in groups[3]["files"]] == ["PS1.pdf"]
    assert _source_role("tutorial", tutorials / "EFDS_ML_Week 0_ps0.pdf") == "tutorial_question"
    assert groups[2]["review_flags"]


def test_generic_tutorial_pdf_is_preserved_as_a_handout():
    assert _source_role("tutorial", Path("Week 1 Tutorial.pdf")) == "tutorial_handout"


def test_tutorial_pages_preserve_question_graphics_and_provided_solutions(tmp_path):
    from module_knowledge.generation import _prepare_tutorial_pages, _tutorial_pages_fragment

    path = tmp_path / "Week 1 Tutorial.pdf"
    document = pymupdf.open()
    question = document.new_page()
    question.insert_text((50, 50), "Exercise: compare project cash flows.")
    question.draw_rect(pymupdf.Rect(50, 70, 150, 130))
    answer = document.new_page()
    answer.insert_text((50, 50), "Solution")
    answer.insert_text((50, 80), "The project creates positive net present value.")
    document.save(path)
    document.close()
    source = {"id": "tutorial", "role": "tutorial_handout", "relative_path": "source/tutorials/Week 1 Tutorial.pdf", "local_path": str(path)}
    note_dir = tmp_path / "notes"
    pages = _prepare_tutorial_pages([source], note_dir)

    assert len(pages) == 2
    assert pages[0]["label"] == "Tutorial question"
    assert pages[1]["label"] == "Provided official tutorial solution"
    assert all((note_dir / p["asset"]).is_file() for p in pages)
    full = _tutorial_pages_fragment(pages, include_sources=True)
    actual = _tutorial_pages_fragment(pages, include_sources=False)
    assert full.count(r"\includegraphics") == actual.count(r"\includegraphics") == 2
    assert "source/tutorials/Week 1 Tutorial.pdf" in full
    assert "source/tutorials/Week 1 Tutorial.pdf" not in actual
    assert r"\sourcecite" not in actual and r"\reviewflag" not in actual
    assert "Provided official tutorial solution" in actual


def test_generate_tutorial_keeps_original_pdf_pages_in_both_editions(tmp_path):
    from module_knowledge.generation import generate_module

    year = tmp_path / "Year 2"
    module = year / "Test Module"
    folder = module / "source/tutorials/2026-10-09_01"
    folder.mkdir(parents=True)
    source = folder / "Week 1 Tutorial.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 50), "Exercise: state the constraint and draw the feasible set.")
    page.draw_rect(pymupdf.Rect(50, 70, 150, 130))
    document.save(source)
    document.close()
    report = generate_module(module, year, academic_year="2026--27", in_module_generated=True, compile_pdfs=False)
    group = report["groups"][0]
    assert group["preserved_tutorial_pages"] == 1
    for key in ("tex", "actual_tex"):
        tex = Path(group[key])
        assert tex.read_text().count(r"\includegraphics") == 1
        evidence = json.loads(tex.with_suffix(".evidence.json").read_text())
        assert len(evidence["assets"]) == 1
        assert evidence["assets"][0]["sha256"]
    assert r"\includegraphics" in Path(report["actual_master"]["tex"]).read_text()


def test_gvfs_source_path_maps_to_matching_gio_mount_uri():
    source = Path(
        "/run/user/1000/gvfs/onedrive:host=imperial.ac.uk,user=student.example/OneDrive/Year 2/Machine Learning/source/lectures/lecture1.pdf"
    )
    mounts = "Mount(0): another@ic.ac.uk -> onedrive://another/\nMount(1): student.example@imperial.ac.uk -> onedrive://imperial-user/\n"

    uri = _gvfs_source_uri(source, mounts)

    assert uri == "onedrive://imperial-user/OneDrive/Year%202/Machine%20Learning/source/lectures/lecture1.pdf"


def test_gvfs_staging_uses_bounded_gio_copy_instead_of_blocking_file_reads(tmp_path, monkeypatch):
    import shutil
    import subprocess

    import module_knowledge.generation as generation

    mount = tmp_path / "gvfs" / "onedrive:host=imperial.ac.uk,user=student.example"
    module_root = mount / "OneDrive" / "Year 2" / "Machine Learning"
    source = module_root / "source" / "lectures" / "2026-10-05_01" / "lecture.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"course source")
    calls = []
    listing = "Mount(1): student.example@imperial.ac.uk -> onedrive://imperial-user/\n"

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-2:] == ["mount", "-l"]:
            return subprocess.CompletedProcess(command, 0, listing, "")
        assert command[1] == "copy"
        shutil.copyfile(source, command[-1])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(generation.shutil, "which", lambda _name: "/usr/bin/gio")
    monkeypatch.setattr(generation.subprocess, "run", fake_run)
    snapshot_root = tmp_path / "snapshot"
    staged, failures = _stage_group(
        {"kind": "lecture", "files": [source]},
        module_root,
        snapshot_root,
        copy_timeout=30,
    )

    assert not failures
    assert staged[0]["role"] == "lecture_slides"
    assert Path(staged[0]["local_path"]).read_bytes() == b"course source"
    assert calls[1][1] == "copy"
    assert "OneDrive/Year%202/Machine%20Learning/" in calls[1][2]


def test_source_copy_timeout_is_reported_without_creating_partial_snapshot(tmp_path, monkeypatch):
    import subprocess

    import module_knowledge.generation as generation

    module_root = tmp_path / "module"
    source = module_root / "source" / "lectures" / "week.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"local source")

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("cp", 1)

    monkeypatch.setattr(generation.subprocess, "run", timeout)
    staged, failures = _stage_group(
        {"kind": "lecture", "files": [source]},
        module_root,
        tmp_path / "snapshot",
        copy_timeout=1,
    )

    assert staged == []
    assert failures[0]["reason"] == "source-copy-timeout"


def test_date_outside_academic_year_is_marked_for_review(tmp_path):
    source = tmp_path / "lecture2.pdf"
    source.touch()
    group = {
        "kind": "lecture",
        "number": "2",
        "relative_dir": "source/lectures/2025-10-12_02",
        "files": [source],
    }

    _, _, shown_date, review_flags = _date_number_title(group, tmp_path, academic_year="2026--27")

    assert "DATE NEEDS REVIEW" in shown_date
    assert any("outside academic year" in flag for flag in review_flags)


def test_filename_date_is_compared_with_folder_date_without_crashing(tmp_path):
    source = tmp_path / "lecture_2026-10-07_captions.txt"
    source.touch()
    group = {
        "kind": "lecture",
        "number": "1",
        "relative_dir": "source/lectures/2026-10-06_01",
        "files": [source],
    }

    _, _, shown_date, review_flags = _date_number_title(
        group, tmp_path, academic_year="2026--27"
    )

    assert shown_date == "DATE NEEDS REVIEW (folder 2026-10-06; source filename 2026-10-07)"
    assert any("source filename(s) say 2026-10-07" in flag for flag in review_flags)


def test_exact_tutorial_text_uses_safe_breaks_before_bracketed_lines():
    relative_path = "source/tutorials/PS1.pdf"
    item = {
        "source_id": "source",
        "relative_path": relative_path,
        "locator": "p. 1",
        "role": "tutorial_question",
        "text": "List of outcomes:\n\n[1, 2, 3]",
        "exact_source_text": True,
        "visual_unreviewed": False,
    }

    body = _body_fragment([item], [], {"source": {"relative_path": relative_path}})

    assert r"List of outcomes:\newline" in body
    assert "\\par\n[1, 2, 3]\\newline" in body


def test_generated_bullets_separate_source_citations():
    relative_path = "source/lectures/lecture1.pdf"
    item = {
        "source_id": "source",
        "relative_path": relative_path,
        "locator": "p. 1",
        "role": "lecture_slides",
        "text": "A generated point.",
        "exact_source_text": False,
        "visual_unreviewed": False,
    }

    body = _body_fragment([item], [], {"source": {"relative_path": relative_path}})

    assert r"\item A generated point. \sourcecite{source/lectures/lecture1.pdf}{p. 1}" in body


def test_actual_body_preserves_note_text_without_sources_or_coverage_metadata():
    items = [
        {
            "source_id": "slides",
            "relative_path": "source/lectures/lecture1.pdf",
            "locator": "p. 1",
            "role": "lecture_slides",
            "text": "A generated point.",
            "exact_source_text": False,
            "visual_unreviewed": True,
        },
        {
            "source_id": "handout",
            "relative_path": "source/tutorials/PS1.pdf",
            "locator": "p. 2",
            "role": "tutorial_question",
            "text": "State the constraint.",
            "exact_source_text": True,
            "visual_unreviewed": False,
        },
        {
            "source_id": "slides",
            "relative_path": "source/lectures/lecture1.pdf",
            "locator": "p. 3",
            "role": "lecture_slides",
            "text": "Source locator: source/lectures/lecture1.pdf | p. 3",
            "exact_source_text": False,
            "visual_unreviewed": False,
        },
    ]
    sources = {
        "slides": {"relative_path": "source/lectures/lecture1.pdf"},
        "handout": {"relative_path": "source/tutorials/PS1.pdf"},
    }

    body = _body_fragment(
        items,
        [{"source_id": "slides", "locator": "p. 3", "reason": "needs_review"}],
        sources,
        include_sources=False,
    )

    assert "A generated point." in body
    assert "State the constraint." in body
    assert "Source locator" not in body and "source/lectures" not in body
    assert r"\paragraph{Question text.}" in body
    assert r"\sourcecite" not in body
    assert "lecture1.pdf" not in body and "PS1.pdf" not in body
    assert "Source coverage" not in body and "needs_review" not in body
    assert "REVIEW:" not in body


def test_body_fragment_renders_structured_nested_notes_with_support_citations():
    parent = {
        "id": "parent",
        "text": "Scarcity constrains choice.",
        "source_id": "slide1",
        "relative_path": "source/lectures/lecture1.pdf",
        "locator": "p. 1",
        "visual_unreviewed": False,
    }
    child = {
        "id": "child",
        "text": "Income and leisure compete under the budget constraint.",
        "source_id": "slide2",
        "relative_path": "source/lectures/lecture1.pdf",
        "locator": "p. 2",
        "visual_unreviewed": True,
    }
    outline = [{
        "heading": "Scarcity and choice",
        "bullets": [{
            "text": parent["text"],
            "support_items": [parent],
            "children": [{"text": child["text"], "support_items": [child], "children": []}],
        }],
    }]
    sources = {
        "slide1": {"relative_path": parent["relative_path"]},
        "slide2": {"relative_path": child["relative_path"]},
    }

    full = _body_fragment([parent, child], [], sources, outline=outline)
    actual = _body_fragment([parent, child], [], sources, include_sources=False, outline=outline)

    assert r"\subsection{Scarcity and choice}" in full
    assert full.count(r"\begin{itemize}") == 2
    assert full.count(r"\sourcecite{") == 2
    assert r"\reviewflag{visual review pending}" in full
    assert r"\sourcecite" not in actual and r"\reviewflag" not in actual
    assert "Scarcity constrains choice." in actual
    assert "Income and leisure compete" in actual


def test_generate_y2_can_write_notes_under_each_module_generated_directory(tmp_path, monkeypatch):
    import module_knowledge.generation as generation

    year_root = tmp_path / "Year 2"
    module_root = year_root / "Test Module"
    lecture = module_root / "source" / "lectures" / "2026-10-06_01"
    lecture.mkdir(parents=True)
    (lecture / "lecture.txt").write_text("source text", encoding="utf-8")
    existing_transcript = module_root / "generated" / "transcripts" / "overview.txt"
    existing_transcript.parent.mkdir(parents=True)
    existing_transcript.write_text("keep this generated asset", encoding="utf-8")

    def draft_items(frozen, _blocks, **_kwargs):
        source = frozen["sources"][0]
        return ([{
            "source_id": source["id"],
            "relative_path": source["relative_path"],
            "locator": "p. 1",
            "role": "lecture_slides",
            "text": "A generated concept.",
            "exact_source_text": False,
            "visual_unreviewed": False,
        }], [{"source_id": source["id"], "locator": "p. 2", "reason": "needs_review"}])

    monkeypatch.setattr(generation, "extract_source", lambda _source: [])
    monkeypatch.setattr(generation, "_draft_group_items", draft_items)

    from module_knowledge.cli import main

    assert main([
        "generate-y2",
        "--year-root", str(year_root),
        "--output-root", str(year_root),
        "--in-module-generated",
        "--academic-year", "2026--27",
        "--no-pdf",
    ]) == 0

    output = module_root / "generated"
    report = json.loads((year_root / "generation-report.json").read_text(encoding="utf-8"))
    assert report["modules"][0]["output_root"] == str(output)
    group = report["modules"][0]["groups"][0]
    full_tex = Path(group["tex"])
    actual_tex = Path(group["actual_tex"])
    full_content = full_tex.read_text(encoding="utf-8")
    actual_content = actual_tex.read_text(encoding="utf-8")
    actual_body = actual_content.split(r"\pagenumbering{arabic}", 1)[1].split(r"\end{document}", 1)[0]
    assert full_tex.name.endswith("_FULL.tex")
    assert actual_tex.name == "Test_Module_lecture_1_2026-10-06_01.tex"
    assert r"\sourcecite" in full_content and "lecture.txt" in full_content
    assert "A generated concept." in actual_body
    assert r"\sourcecite" not in actual_body and "lecture.txt" not in actual_body
    assert r"\section*{Source coverage and review gaps}" in full_content
    assert r"\section*{Source coverage and review gaps}" not in actual_body
    full_master = Path(report["modules"][0]["master"]["tex"])
    actual_master = Path(report["modules"][0]["actual_master"]["tex"])
    actual_master_body = actual_master.read_text(encoding="utf-8").split(
        r"\pagenumbering{arabic}", 1
    )[1].split(r"\end{document}", 1)[0]
    assert full_master.name == "Test-Module_MASTER_FULL.tex"
    assert actual_master.name == "Test-Module_MASTER.tex"
    assert r"\sourcecite" in full_master.read_text(encoding="utf-8")
    assert "A generated concept." in actual_master_body
    assert r"\sourcecite" not in actual_master_body and "lecture.txt" not in actual_master_body
    assert existing_transcript.read_text(encoding="utf-8") == "keep this generated asset"
    assert not (year_root / "Test-Module").exists()
    assert (year_root / "generation-report.json").is_file()
