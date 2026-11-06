# module-knowledge

Local-first, source-linked note creation from selected course materials. The current output contract is LaTeX for Econometrics 1, Machine Learning, Microeconomics 2, and Corporate Finance and Capital Markets, as recorded in `config/module-formats.json`.

Status: a reusable LaTeX renderer, article template, provenance manifest, lecture/tutorial combiner, and pinned PDF toolchain are implemented. The `generate-y2` command discovers course lecture and tutorial materials, snapshots sources, drafts local evidence-linked notes, emits individual and master `.tex` files, and compiles PDFs. DOCX note generation is retired; historical/reference DOCX files are not deleted automatically.

Start with [the Machine Learning weeks 1–5 preparation guide](docs/machine-learning-weeks-1-5.md) for scoped runs, the new material folders, and a read-only input preview. The general [LaTeX note workflow](docs/latex-note-workflow.md) documents the renderer and toolchain. The [architecture](docs/architecture.md) describes the wider evidence and evaluation pipeline. [The older Accounting DOCX evaluation plan](docs/note-writing-evaluation-plan.md) is retained as historical design material, not the active output-format decision. The read-only Year 1 coursework assessment is a private local document, excluded from Git; it records personal inventory metadata and source gaps.

Note feedback persists across sessions through [the feedback-learning workflow](docs/feedback-learning.md), `config/note-preferences.json`, and the private edit history linked there. Active preferences are included in drafting/consolidation prompts and recorded in generated manifests. Agents start from `AGENTS.md`; reviewers still supply only File, Page and Suggested change.

Private source files, extracted text, model inputs/outputs, generated notes and build artefacts belong in a private data directory outside this project tree. Do not commit course materials or generated notes here.

## Install and test

Requires Python 3.12–3.14 and [uv](https://docs.astral.sh/uv/):

    git clone https://github.com/slee7286/module-knowledge.git
    cd module-knowledge
    uv sync --locked --extra test
    uv run module-knowledge --help
    uv run pytest -q

Install the pinned PDF compiler with `sh scripts/install-tectonic.sh` before compiling PDFs. See the LaTeX workflow for compiler and local-model requirements; unit tests do not require a running model server.

For manually agent-authored notes, native source reconstruction and inter-week permission gates, see [the authoring acceptance checklist](docs/agent-note-authoring.md). Course-specific builders and transcriptions remain private rather than being presented as generic CLI functionality.

## Repository history

The initial commit series imports the existing implementation in logical feature groups. These are present-day commits, not recovered or backdated development history. The repository contains reusable system code and procedures, not the private course-note runs.
