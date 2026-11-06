import json

import pymupdf

from module_knowledge.cli import main
from module_knowledge.render import render_latex


def test_cli_extract_reads_only_a_frozen_private_snapshot(tmp_path, capsys):
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "A budget allocates anticipated resources to a future period.")
    source = tmp_path / "copied.pdf"
    pdf.save(source)
    run = tmp_path / "private-run"
    run.mkdir()
    (run / "frozen-development.json").write_text(json.dumps({"slice": "development", "sources": [{"id": "s1", "sha256": "x", "role": "lecture_handout", "relative_path": "Lecture 2/copied.pdf", "local_path": str(source)}]}))

    assert main(["extract", "--run", str(run)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["blocks"] == 1
    assert (run / "evidence-development.jsonl").exists()

    assert main(["baseline", "--run", str(run)]) == 0
    baseline = json.loads((run / "baseline-development.json").read_text())
    assert baseline["model"] == "extractive-floor"
    assert baseline["items"][0]["locator"] == "p.1"

    assert main(["render", "--run", str(run), "--variant", "baseline"]) == 0
    assert (run / "Accounting-development-baseline.tex").exists()
    assert not (run / "Accounting-development-baseline.docx").exists()


def test_cli_build_latex_assembles_manifest_body_with_packaged_template(tmp_path, capsys):
    body = tmp_path / "lecture.tex"
    body.write_text(r"\subsection{Model}" + "\n" + r"\[y_i=\beta x_i+\epsilon_i\]" + "\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "module": "Econometrics 1",
                "title": "Econometrics 1 Notes",
                "academic_year": "2026--27",
                "lectures": [
                    {"number": 1, "title": "SLR", "date": "6 October 2026", "body_file": "lecture.tex"}
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "notes.tex"

    assert main(["build-latex", "--manifest", str(manifest), "--output", str(output)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["format"] == "latex"
    assert r"\tableofcontents" in output.read_text(encoding="utf-8")
    assert r"\section{Lecture 1: SLR (6 October 2026)}" in output.read_text(encoding="utf-8")


def test_cli_build_master_combines_components_and_writes_report(tmp_path, capsys):
    body = tmp_path / "body.tex"
    body.write_text(r"\subsection{Demand}" + "\n" + "Consumer choice.", encoding="utf-8")
    component = tmp_path / "lecture.tex"
    render_latex(
        {
            "module": "Microeconomics 2",
            "lectures": [{
                "number": 1,
                "title": "Consumer choice",
                "date": "5 October 2026",
                "body_file": "body.tex",
            }],
        },
        component,
        source_root=tmp_path,
    )
    output = tmp_path / "master.tex"

    assert main([
        "build-master",
        "--module", "Microeconomics 2",
        "--academic-year", "2026--27",
        "--component", str(component),
        "--output", str(output),
    ]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["component_count"] == 1
    assert r"\section{Lecture 1: Consumer choice (5 October 2026)}" in output.read_text(encoding="utf-8")
