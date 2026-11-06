import json
import hashlib

from module_knowledge.latex import _escape_tex
from module_knowledge.render import render_latex


def test_render_latex_builds_toc_dated_lecture_and_provenance_sidecar(tmp_path):
    body = tmp_path / "lecture-1.tex"
    body.write_text(r"\subsection{Linear model}" + "\n" + r"\[y_i=\beta x_i+\epsilon_i\]" + "\n", encoding="utf-8")
    source = tmp_path / "slides.pdf"
    source.write_bytes(b"official source bytes")
    draft = {
        "module": "Econometrics 1",
        "title": "Econometrics 1 Notes",
        "academic_year": "2026--27",
        "processing": {"asr_model": "Systran/faster-whisper-medium.en", "revision": "fixed"},
        "source_files": [
            {"id": "slides", "role": "lecture_slides", "path": "slides.pdf", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        ],
        "lectures": [
            {
                "number": 1,
                "title": "Simple Linear Regression",
                "date": "6 October 2026",
                "body_file": "lecture-1.tex",
                "sources": [{"path": "lecture-slides.pdf", "locator": "PDF p. 74"}],
            }
        ],
    }
    output = tmp_path / "Econometrics-1.tex"

    result = render_latex(draft, output, source_root=tmp_path)

    tex = output.read_text(encoding="utf-8")
    assert r"\documentclass" in tex
    assert r"\tableofcontents" in tex
    assert r"\section{Lecture 1: Simple Linear Regression (6 October 2026)}" in tex
    assert r"\[y_i=\beta x_i+\epsilon_i\]" in tex
    assert result["format"] == "latex"
    sidecar = json.loads(output.with_suffix(".evidence.json").read_text(encoding="utf-8"))
    assert sidecar["sources"][0]["locator"] == "PDF p. 74"
    assert sidecar["processing"]["revision"] == "fixed"
    assert sidecar["inputs"][0]["path"] == "lecture-1.tex"
    assert any(entry["path"] == "slides.pdf" for entry in sidecar["inputs"])


def test_render_latex_renders_flat_pipeline_drafts_as_cited_bullets(tmp_path):
    draft = {
        "module": "Accounting",
        "slice": "development",
        "model": "local",
        "items": [
            {
                "id": "i1",
                "text": "Sales & cash budgets.",
                "source_id": "src1",
                "relative_path": "Lecture 2/handout.pdf",
                "locator": "p.3",
                "role": "lecture_handout",
                "fact_checked": False,
                "visual_unreviewed": False,
            }
        ],
        "skipped": [{"source_id": "src1", "locator": "p.4", "reason": "needs_visual_review"}],
    }
    output = tmp_path / "Accounting.tex"

    result = render_latex(draft, output, label="Lecture 2")

    tex = output.read_text(encoding="utf-8")
    assert r"\section{Lecture 2}" in tex
    assert r"Sales \& cash budgets." in tex
    assert r"\sourcecite{Lecture 2/handout.pdf}{p.3}" in tex
    assert r"needs\_visual\_review" in tex
    assert not (tmp_path / "Accounting.docx").exists()
    assert result["draft_items"] == 1


def test_render_latex_rejects_body_fragments_outside_the_manifest_root(tmp_path):
    draft = {
        "module": "Econometrics 1",
        "lectures": [
            {"number": 1, "title": "SLR", "date": "6 October 2026", "body_file": "../outside.tex"}
        ],
    }

    try:
        render_latex(draft, tmp_path / "notes.tex", source_root=tmp_path)
    except ValueError as error:
        assert "inside the manifest root" in str(error).lower()
    else:
        raise AssertionError("body fragment traversal must be rejected")


def test_render_latex_rejects_changed_source_bytes_against_manifest_hash(tmp_path):
    (tmp_path / "body.tex").write_text(r"\subsection{Content}", encoding="utf-8")
    (tmp_path / "slides.pdf").write_bytes(b"changed")
    draft = {
        "module": "Econometrics 1",
        "source_files": [{"path": "slides.pdf", "sha256": "0" * 64}],
        "lectures": [{"number": 1, "title": "SLR", "date": "6 October 2026", "body_file": "body.tex"}],
    }

    try:
        render_latex(draft, tmp_path / "notes.tex", source_root=tmp_path)
    except ValueError as error:
        assert "sha-256" in str(error).lower()
    else:
        raise AssertionError("source hash mismatch must be rejected")


def test_render_latex_resolves_evidence_from_a_separate_module_root(tmp_path):
    notes_root = tmp_path / "notes" / "2026-10-06_01"
    notes_root.mkdir(parents=True)
    (notes_root / "body.tex").write_text(r"\subsection{Content}", encoding="utf-8")
    source_root = tmp_path / "source" / "lectures" / "2026-10-06_01"
    source_root.mkdir(parents=True)
    (source_root / "slides.pdf").write_bytes(b"slides")
    draft = {
        "module": "Econometrics 1",
        "source_files": [{"path": "source/lectures/2026-10-06_01/slides.pdf", "role": "lecture_slides"}],
        "lectures": [{"number": 1, "title": "SLR", "date": "6 October 2026", "body_file": "body.tex"}],
    }

    result = render_latex(
        draft,
        notes_root / "notes.tex",
        source_root=notes_root,
        evidence_root=tmp_path,
    )

    sidecar = json.loads((notes_root / "notes.evidence.json").read_text(encoding="utf-8"))
    assert result["input_files"] == 2
    assert sidecar["inputs"][1]["path"] == "source/lectures/2026-10-06_01/slides.pdf"


def test_render_latex_omits_visible_sources_but_keeps_provenance_sidecar(tmp_path):
    body = tmp_path / "body.tex"
    body.write_text(
        r"\subsection{Notes}" + "\n"
        + r"\item Data source: lecture_slides, source/lectures/week1.pdf | p. 1" + "\n"
        + r"A key point. \sourcecite{slides.pdf}{p. 1}",
        encoding="utf-8",
    )
    source = tmp_path / "slides.pdf"
    source.write_bytes(b"source bytes")
    draft = {
        "module": "Econometrics 1",
        "source_files": [{"path": "slides.pdf", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
        "lectures": [{
            "number": 1,
            "title": "Regression",
            "date": "6 October 2026",
            "body_file": "body.tex",
            "sources": [{"path": "slides.pdf", "locator": "p. 1"}],
            "review_flags": ["Review figure on slides.pdf p. 1"],
        }],
    }
    output = tmp_path / "actual.tex"

    render_latex(draft, output, source_root=tmp_path, include_sources=False)

    tex = output.read_text(encoding="utf-8")
    body = tex.split(r"\pagenumbering{arabic}", 1)[1].split(r"\end{document}", 1)[0]
    sidecar = json.loads(output.with_suffix(".evidence.json").read_text(encoding="utf-8"))
    assert "A key point." in body
    assert r"\sourcecite" not in body
    assert "slides.pdf" not in body
    assert "source/lectures" not in body
    assert "REVIEW:" not in body
    assert "source-linked study notes" not in tex
    assert "CITATION-FREE STUDY NOTES" in tex
    assert sidecar["sources"][0]["path"] == "slides.pdf"


def test_render_latex_refuses_to_overwrite_its_body_fragment(tmp_path):
    body = tmp_path / "notes.tex"
    original = r"\subsection{Keep this source fragment}"
    body.write_text(original, encoding="utf-8")
    draft = {
        "module": "Econometrics 1",
        "lectures": [{"number": 1, "title": "SLR", "date": "6 October 2026", "body_file": "notes.tex"}],
    }

    try:
        render_latex(draft, body, source_root=tmp_path)
    except ValueError as error:
        assert "overwrite" in str(error).lower()
    else:
        raise AssertionError("output must not overwrite a manifest input")
    assert body.read_text(encoding="utf-8") == original


def test_escape_tex_preserves_curly_quotes_and_bullet_glyphs():
    assert _escape_tex("‘pass’ • two histograms") == "``pass'' \\textbullet{} two histograms"


def test_escape_tex_converts_common_math_glyphs_for_pdf_rendering():
    assert _escape_tex("ˆy + c′(y) ≃ 0 ⇒ µ ≠ δ; ϵ = 2⁻¹") == (
        r"$\hat{y}$ + c'(y) $\simeq$ 0 $\Rightarrow$ $\mu$ $\neq$ $\delta$; "
        r"$\varepsilon$ = 2\textsuperscript{-1}"
    )


def test_escape_tex_makes_extracted_symbol_loss_visible():
    assert _escape_tex("困境 Y̸=f(X), Y̸ = f(X) x̃ \uf8eb\uf8f6") == (
        r"[unrendered CJK text] Y $\neq$ f(X), Y $\neq$ f(X) $\tilde{x}$ ()"
    )


def test_template_separates_front_matter_and_note_page_numbering(tmp_path):
    draft = {"module": "Econometrics 1", "slice": "development", "items": [], "skipped": []}
    output = tmp_path / "notes.tex"

    render_latex(draft, output)

    tex = output.read_text(encoding="utf-8")
    assert tex.index(r"\pagenumbering{Roman}") < tex.index(r"\begin{titlepage}")
    assert tex.index(r"\pagenumbering{roman}") > tex.index(r"\end{titlepage}")
    assert tex.index(r"\pagenumbering{arabic}") > tex.index(r"\tableofcontents")


def test_typed_source_commentary_is_full_only_in_components_and_masters(tmp_path):
    from module_knowledge.latex import combine_latex_notes

    body = tmp_path / "body.tex"
    body.write_text(
        r"\subsection{Concept}" + "\n"
        + r"A useful explanation with a correctness condition: assume full rank. "
        + r"\sourceinfo{A delivery comparison with \textbf{nested braces} and $x_{i}$.} "
        + r"Read \texttt{source/data.csv} as the example input.",
        encoding="utf-8",
    )
    draft = {"module": "Example", "lectures": [{"number": 1, "title": "Concept",
             "date": "Unconfirmed", "body_file": "body.tex"}]}
    full = tmp_path / "full.tex"
    clean = tmp_path / "clean.tex"
    render_latex(draft, full, source_root=tmp_path, include_sources=True)
    render_latex(draft, clean, source_root=tmp_path, include_sources=False)
    combine_latex_notes([full], tmp_path / "master.tex", module="Example",
                        academic_year="2026", include_sources=False)
    assert r"\newcommand{\sourceinfo}" in full.read_text()
    assert "A delivery comparison" in full.read_text()
    for path in (clean, tmp_path / "master.tex"):
        content = path.read_text().split(r"\pagenumbering{arabic}", 1)[1]
        assert "A delivery comparison" not in content
        assert r"\sourceinfo" not in content
        assert "assume full rank" in content
        assert r"source/data.csv" in content
