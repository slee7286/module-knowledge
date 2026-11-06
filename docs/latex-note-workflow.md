# LaTeX note workflow

## Output decision

`config/module-formats.json` sets LaTeX as the default and the shared `module-notes` template for Econometrics 1, Machine Learning, Microeconomics 2, and Corporate Finance and Capital Markets. The end-to-end workflow produces paired PDFs for each lecture, tutorial, and master: `*_FULL.pdf` retains source citations and review/coverage information, while the corresponding unsuffixed `.pdf` omits visible citations and review metadata. Both LaTeX sources and provenance sidecars remain alongside the PDFs; the renderer does not write DOCX notes. Existing historical/reference DOCX files are not deleted automatically.

The shared template is `src/module_knowledge/templates/module-notes.tex`. It creates an A4 document with a title page, contents, dated lecture sections, compact topic headings, equations, figures/tables, and exact source locators. Lecture dates are required in manifest-based builds; do not infer a date from a filename.

## Generate all Year 2 lecture and tutorial notes

`module-knowledge generate-y2` is the end-to-end local workflow. It discovers every Year 2 module directory with `source/` or `sources/` lecture/tutorial folders, snapshots supported source files, extracts anchored evidence, drafts with a loopback-only local Ollama model, then performs a provenance-preserving outline pass that groups points under topic subheadings and nested bullets. Identical points are collapsed within each event; exact repeats across later events are replaced by a cross-reference to the first event. Multi-batch outlines receive a second consolidation pass even if the first pass only reorganizes the same number of points. Invalid large JSON/schema responses are retried in smaller batches with bounded depth; transport failures are not multiplied into retries. Unassigned points remain in an explicit fallback and both recovered and unrecovered failures are recorded. ID-only model bullets are restored from their canonical input text without losing nesting; IDs embedded in generated prose are rejected into the source-preserving fallback. Restoration is reported for organization review, and compiled PDFs must be checked for internal ID tokens before handoff. All supporting source locators are retained in the full edition. The workflow writes one standalone `.tex` note per lecture/tutorial (or numbered problem set), combines those notes into a module master, and compiles PDFs with the pinned Tectonic script.

```sh
.venv/bin/module-knowledge generate-y2 \
  --year-root "/path/to/OneDrive/Year 2" \
  --output-root "$HOME/.local/share/module-knowledge/y2/2026-27" \
  --academic-year "2026--27"
```

The default models are `qwen3:8b` and `qwen3-vl:8b-instruct` at `http://127.0.0.1:11434`; override them with `--model`, `--visual-model`, or `--endpoint` (the generator only accepts explicit loopback HTTP). Use `--no-pdf` for a LaTeX-only pass. Each module output contains a read-only source snapshot, per-event full/actual manifests and LaTeX sources, provenance sidecars, paired individual PDFs, paired master PDFs, and `generation-report.json`. The year root gets a combined report. Per-block model checkpoints make interrupted runs resumable; source copies have a 45-second timeout and failures are recorded rather than blocking the whole run. For GNOME OneDrive sources, the runner resolves the mounted account URI and uses `gio copy`; do not replace this with `cp` or a direct Python file read, which can remain stuck in an uninterruptible GVfs wait. If the GIO transfer also times out, make the source files available locally and rerun rather than retrying indefinitely.

The generator now also supports explicit lecture-slides/transcripts, problem-sets/solutions, tutorial-slides, miscellaneous, mock-tests/solutions and midterm-study-guides folders. See [the scoped Machine Learning guide](machine-learning-weeks-1-5.md) for the exact layout, `source-map.json`, module/week selection, safe named output directories and `--dry-run`. Readings, administrative material, and audio/video files remain excluded; in particular MP4/M4A files are not processed. New scoped runs require a fresh `--run-name`; unlike the legacy unscoped output, a named run is not overwritten or automatically resumed. Tutorial question sheets and tutorial handouts are retained as source content rather than answered by the model; explicit solution files remain separate and are not merged into questions. Tutorial PDF pages are reproduced directly at readable resolution in both editions, preserving question wording, tables, figures and notation; pages explicitly headed “Solution” are labelled as provided official tutorial solutions. Page images are hashed in the manifests and evidence sidecars, and the clean edition omits the added source citations. Non-PDF tutorial code/handouts retain their extracted text, so DOCX equations and drawings still require source comparison. Low-text pages may be transcribed locally by the visual model, but model-transcribed or diagram-heavy content is marked for human review. Conflicting or missing dates/numbers and sources that fail to copy/extract are reported as review gaps. These are drafts, not verified final notes. A source DOCX may be read as input, but this workflow generates no DOCX files.

## Stage OneDrive files in a local directory

`scripts/sync_onedrive.py` uses rclone's OneDrive backend instead of copying from the GNOME/GVfs mount, whose remote reads may stall. Install rclone (`sudo apt install rclone`) and configure a OneDrive remote with `rclone config` if one is not already present. `rclone listremotes` shows the configured remote names; use that name to the left of `:` in the commands below. This machine's configured OneDrive remote is `siheon:`. Keep the rclone config private; it contains refresh credentials.

Preview a copy of the Year 2 folder, excluding MP4s:

```sh
python3 scripts/sync_onedrive.py --dry-run --exclude '*.mp4' 'siheon:Year 2'
```

Run the initial download and later incremental updates with the same command, omitting `--dry-run`:

```sh
python3 scripts/sync_onedrive.py --exclude '*.mp4' 'siheon:Year 2'
```

The default local destination is `/home/siheon/projects/OneDrive`. `rclone copy --checksum` checks the OneDrive hashes and transfers new or changed files; it does not delete destination files that were removed remotely. Treat the synced source folders as read-only; the generation workflow writes only into each module's dedicated `generated/` subdirectory. Use `--destination PATH` to choose another local directory and repeat `--exclude PATTERN` for additional exclusions. To copy the entire account rather than a selected folder, explicitly pass `--all 'siheon:'`; review the dry run and available disk space first.

To keep each module's outputs beside its sources, in `<module>/generated/`, run:

```sh
.venv/bin/module-knowledge generate-y2 \
  --year-root '/home/siheon/projects/OneDrive' \
  --output-root '/home/siheon/projects/OneDrive' \
  --in-module-generated \
  --academic-year '2026--27'
```

The combined `generation-report.json` is written at the Year 2 root; each per-module report and all note/source artifacts are under that module's `generated/` directory. The default external-output mode remains available by setting `--output-root` to a separate destination and omitting `--in-module-generated`.

## Human review

Use the source-linked `*_FULL.pdf` for review and the unsuffixed `.pdf` as a clean reading copy. The clean copy omits citations, review flags, and skipped-block coverage warnings, so do not use it to verify source fidelity. See [`note-review-guide.md`](note-review-guide.md) for a repeatable checklist and a format for returning corrections and interpretations.

To combine already generated component notes manually:

```sh
.venv/bin/module-knowledge build-master \
  --module "Microeconomics 2" --academic-year "2026--27" \
  --component "$NOTES/lecture-one.tex" \
  --component "$NOTES/tutorial-one.tex" \
  --output "$NOTES/Microeconomics_2_MASTER.tex"
```

Run `.venv/bin/pytest -q` after changing the workflow. The master document uses the same template and retains child source provenance in its evidence sidecar.

## Build a note from a manifest

Keep private manifests, body fragments, figures and output outside the repository. A minimal manifest has this shape:

```json
{
  "module": "Econometrics 1",
  "title": "Econometrics 1 — Lecture 1: Simple Linear Regression",
  "academic_year": "2026--27",
  "source_files": [
    {"id": "slides", "role": "lecture_slides", "path": "source/lectures/DATE/slides.pdf", "sha256": "..."}
  ],
  "lectures": [
    {
      "number": 1,
      "title": "Simple Linear Regression",
      "date": "6 October 2026",
      "body_file": "lecture-01-body.tex",
      "sources": [{"path": "source/lectures/DATE/slides.pdf", "locator": "PDF pp. 1--20"}]
    }
  ],
  "assets": ["figures/slide-01.png"]
}
```

The body fragment is trusted LaTeX content and may contain `\subsection`, math environments, tables, figures and `\sourcecite{source}{locator}`. `body_file` and `assets` resolve relative to the manifest directory. `source_files` resolve relative to the evidence root. The renderer rejects path traversal and mismatched declared SHA-256 hashes. It writes a `.evidence.json` sidecar containing hashes of the template, body, source files, assets and final `.tex`.

```sh
.venv/bin/module-knowledge build-latex \
  --manifest "$MODULE_ROOT/notes/DATE/manifest.json" \
  --evidence-root "$MODULE_ROOT" \
  --output "$MODULE_ROOT/notes/DATE/Module_Lecture_DRAFT.tex"
```

The existing `render` command also emits `.tex` from the pipeline's flat, source-anchored draft JSON. It preserves locators and review gaps; it does not emit Word files.

## Compile the PDF companion

The PDF is a rendered preview; `.tex` remains the editable canonical note. Tectonic is pinned in `tools/tectonic.lock.json` (0.17.0, Linux x86_64 GNU build, SHA-256 verified). Install the pinned binary and compile with:

```sh
sh scripts/install-tectonic.sh
sh scripts/build-pdf.sh "$MODULE_ROOT/notes/DATE/Module_Lecture_DRAFT.tex"
```

The first compile downloads Tectonic's TeX support bundle; subsequent runs use its local cache. The build script checks the engine version and reruns LaTeX twice for the table of contents. Review the resulting PDF, not only the source: check TOC, dated headings, equations, figure/table placement and page layout.

## Reproduce the optional podcast transcript

The local ASR script is `scripts/transcribe_audio.py`; its exact package versions are in `tools/transcription-requirements.lock`, and the model commit and decoding options are fixed in the script. Setup (downloads the pinned model revision) and run locally:

```sh
sh scripts/prepare-transcription.sh
"$HOME/.local/share/module-knowledge/tools/whisper-env/bin/python" \
  scripts/transcribe_audio.py \
  "$MODULE_ROOT/source/lectures/DATE/podcast.m4a" \
  "$HOME/.local/share/module-knowledge/models/faster-whisper-medium.en" \
  "$MODULE_ROOT/generated/transcripts/DATE/podcast_transcript.txt"
```

This uses CPU/int8 and does not upload the audio. Transcript segments have approximate timestamps; verify technical claims against the official slides and lecture extract.

## Current Econometrics 1 draft

The Lecture 1 manifest, body, figures, generated `.tex`, provenance sidecar and compiled PDF are under the private module data root at `notes/2026-10-06_01/`. The manifest pins the PDF, captions, M4A and transcript hashes, the ASR model revision/settings, five reviewed slide figures, and exact per-claim locators. The AI podcast is treated as secondary and its uncertainties are called out in the notes.

The student's Year 1 style references are accessible on the configured OneDrive remote and were inspected in DOCX/PDF, LaTeX, notebook, and R Markdown forms. The Microeconomics 1 DOCX uses dated contents entries and Word list levels 0–2; the Mathematical Foundations LaTeX notes use nested `itemize` lists; the notebook has a detailed hierarchical contents page; and the IDS Rmd uses concise nested overview bullets and explicitly avoids repeating tutorial concepts already explained in lectures. The Year 2 outline pass follows those conventions with dated event headings, topic subheadings, concise British-English phrasing, nested definitions/assumptions/examples, and source-preserving repeat consolidation. It remains a draft until the source-linked human review in `note-review-guide.md` is complete.
