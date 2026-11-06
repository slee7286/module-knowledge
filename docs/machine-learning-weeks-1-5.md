# Machine Learning: weeks 1–5

This prepares a later run. It does not download materials, start a model server or generate course notes.

## 1. Add the materials

Module root: `/home/siheon/projects/OneDrive/Machine Learning`.

Use these directories under `source/` (the same structure works under `sources/`):

```text
source/
  lecture-slides/Week 1/lecture1.pdf
  lecture-transcripts/Week 1/transcript.txt
  problem-sets/Week 1/PS1.pdf
  problem-set-solutions/Week 1/PS1_solutions.pdf
  tutorial-slides/Week 1/tutorial.pdf
  miscellaneous/Week 1/cheatsheet.pdf
  miscellaneous/Week 1/mentimeter.pdf
  mock-tests/Week 1-5/mock1.pdf
  mock-test-solutions/Week 1-5/mock1_solutions.pdf
  midterm-study-guides/Week 1-5/guide.pdf
```

Repeat the weekly directories for weeks 2–5. Multi-week papers/guides remain intact under `Week 1-5`; do not split their pages between weeks. A paper labelled `Week 1-6` is reported as a partial overlap and excluded from a weeks 1–5 run.

Existing `source/lectures/<dated-event>/` and `source/tutorials/<dated-event>/` layouts still work. Do not duplicate the same materials into both layouts. Directory categories also accept spaces or underscores instead of hyphens (for example `lecture slides`). File paths and original files are never renamed. Supported inputs: `.pdf`, `.pptx`, `.docx`, `.txt`, `.py`. Prefer PDF for questions, solutions and equation-heavy handouts, and TXT for transcripts. Other formats, including recordings, are listed but not processed.

Separate slide/transcript directories for the same explicit week are combined into one lecture group. If a week has multiple lectures, use the existing dated-event layout and map each event explicitly instead; do not rely on the one-lecture-per-week convenience layout. Tutorial handouts and standalone problem sets/solutions remain identifiable components.

## 2. Declare weeks and verified dates

A lecture number or problem-set number is not automatically a teaching week. A week must appear as `Week 1`/`Week 1-5` in a path, or be declared in the module's optional `source-map.json`.

Use `/home/siheon/projects/module-knowledge/config/source-map.example.json` as a syntax example. Create your private map at:

```text
/home/siheon/projects/OneDrive/Machine Learning/source-map.json
```

Its top-level `sources` object maps module-relative file or folder paths to metadata. Each entry needs `weeks`, a nonempty array of teaching-week integers. Optional `date` is the verified teaching date in `YYYY-MM-DD` form, not the upload date. A file-specific entry overrides a folder entry; otherwise the longest matching folder entry wins. Metadata overrides path-based week labels. Only `weeks` and `date` fields are accepted.

For example, after verifying that a dated lecture folder belongs to week 1, map that exact folder to `{"weeks": [1]}`. Add its date only after checking the course schedule. Do not copy example dates or silently correct the existing 2025/2026 conflicts. Unmapped dates remain review flags. Existing week-0 preparatory materials are identified but excluded from weeks 1–5.

## 3. Preview without writes or inference

From `/home/siheon/projects/module-knowledge`:

```sh
sh scripts/machine-learning-weeks-1-5.sh
```

This defaults to `preview`. It calls the real CLI with:

```sh
.venv/bin/module-knowledge generate-y2 \
  --year-root '/home/siheon/projects/OneDrive' \
  --output-root '/home/siheon/projects/OneDrive' \
  --in-module-generated \
  --academic-year '2026--27' \
  --module 'Machine Learning' \
  --weeks 1-5 \
  --run-name weeks-1-5 \
  --dry-run
```

Inspect `selected_count`, every file's `status`, `warnings`, `groups`, `output_root` and `run_exists`. The preview inventories files but does not extract their contents or verify their mathematical correctness. It does not require Ollama and creates no output directories.

Status meanings:

- `selected`: included in the planned run.
- `outside-week-scope`: no overlap with the selected weeks.
- `partial-week-overlap`: spans selected and unselected weeks; requires a scope decision.
- `unassigned-week`: add a week label or source-map entry before expecting inclusion.
- `unsupported-format`: convert/provide a supported counterpart.
- `excluded-category`: outside the supported categories, including readings, administrative files, and nested generated/reference-note folders.
- `excluded-symlink`: deliberately not followed.

Missing slides, transcripts, questions, supplied solutions and tutorial handouts are reported per selected week. Warnings do not themselves establish completeness, and missing material is not fabricated. Missing dates and mapping conflicts need review. A zero-selected-source generation is rejected before writing.

## 4. Check local prerequisites, then generate

The default synthesis backend is local Ollama at `http://127.0.0.1:11434`, with `qwen3:8b` and `qwen3-vl:8b-instruct`. Install/start Ollama and make those models available before a lecture/supplement synthesis run. The preparation check found the pinned Tectonic binary installed, but no listening Ollama service and no `ollama` executable on PATH. The preview remains usable without them.

The underlying CLI permits `--endpoint`, `--model`, `--visual-model`, and `--no-pdf`. Explicit loopback HTTP is required. Named runs that require synthesis check the model service and both model names before reserving output directories. Original question/solution PDFs can be reproduced without model inference.

After reviewing the inventory and making the models available:

```sh
sh scripts/machine-learning-weeks-1-5.sh run
```

Output:

```text
/home/siheon/projects/OneDrive/Machine Learning/generated/runs/weeks-1-5/
```

This contains `input-inventory.json`, snapshots, component manifests/bodies, evidence sidecars, paired clean/`_FULL` notes and masters, and `generation-report.json`. Original questions, solutions, supplementary PDFs and study-guide PDFs are preserved as rendered original-page assets. Supplementary materials and study guides also pass through the source-grounded synthesis path. Supplied solutions are labelled separately; no missing official answer is invented. Non-PDF extracted questions/solutions still require comparison for drawings and equation fidelity.

The script requires the explicit word `run` to generate. A named directory is reserved atomically and cannot be reused, even after an interrupted run. Existing generated notes and earlier named runs are untouched. For a new revision:

```sh
sh scripts/machine-learning-weeks-1-5.sh preview weeks-1-5-v2
sh scripts/machine-learning-weeks-1-5.sh run weeks-1-5-v2
```

Do not launch both versions at once. `ONEDRIVE_ROOT` can override the clone root for fixture testing. No automatic OneDrive sync/upload is performed. Named runs do not replace the old root-level generation report; use the report inside the exact run directory.

## 5. Review the results

Read `_FULL.pdf` first and compare all source gaps, equations, figures, dates, questions and supplied answers. Then inspect the rendered clean PDF. A compiled draft is not a verified final set of notes. Use `docs/note-review-guide.md` for corrections and sign-off. Retain the private original sources, manifests and sidecars with the PDFs.

After changing the implementation, run `.venv/bin/pytest -q`.
