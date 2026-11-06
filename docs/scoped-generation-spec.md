# Scoped course-material generation

## Objective and acceptance contract
Prepare the existing local LaTeX pipeline for a later Machine Learning weeks 1–5 run, without generating notes or editing course sources now.

- Discover lecture transcripts/slides, problem sets/solutions, tutorial slides, miscellaneous resources, mock tests/solutions and midterm study guides under source/ or sources/.
- Preserve original question/solution PDF pages, keep supplied answers distinct, and never generate missing answers.
- Select modules by exact directory name and weeks by explicit week labels or an optional source-map.json. Do not silently equate a lecture/problem-set number with a teaching week.
- Provide a read-only JSON preview accounting for every input, including unsupported, out-of-scope and unassigned files and missing expected weekly materials.
- Isolate a named run beneath each module's generated/runs/ directory. Refuse reuse of a populated named run rather than overwrite existing notes.
- Keep the old unfiltered invocation compatible. New scoped runs require a run name.
- Emit resource chapters with truthful names rather than label mock papers as tutorials.

## Commands
Test: .venv/bin/pytest -q
Preview: .venv/bin/module-knowledge generate-y2 --year-root /home/siheon/projects/OneDrive --output-root /home/siheon/projects/OneDrive --in-module-generated --academic-year 2026--27 --module 'Machine Learning' --weeks 1-5 --run-name weeks-1-5 --dry-run
Generation: same command without --dry-run, after inspecting the preview and supplying the source files and local models.

## Structure and style
Extend src/module_knowledge/generation.py and cli.py, with inventory/scope helpers in a dedicated Python module. Extend the existing LaTeX manifest with resources while preserving lectures/tutorials. Tests belong in tests/; operating instructions belong in docs/. Use existing snake_case functions, Path arguments and JSON-compatible dictionary reports. Example report entry: {"path": "source/mock-tests/Week 1-5/mock1.pdf", "status": "selected", "weeks": [1, 2, 3, 4, 5]}.

## Testing strategy
Use pytest, starting each behavior slice with a failing regression. Test complete folder discovery, exact module/week scoping, explicit metadata, exclusion accounting, preview no-write behavior, named-run isolation, exact source preservation, truthful resource headings and both editions. Run the complete existing suite. Exercise the real CLI preview against the local OneDrive clone without model calls. Compile and inspect a synthetic, clearly labelled fixture if the installed PDF toolchain is available; do not represent fixture output as course notes.

## Boundaries
Always: keep source trees read-only; retain provenance; report date/source gaps; use local loopback models only.
Ask first: new dependencies or changes to output format.
Never: start the user's notes run, overwrite previous named runs, fabricate dates or official answers, modify existing course files, commit private materials.

## Known limits
The user will provide the new materials later. Readiness now means code/tests/preview work, not that source completeness or model availability has been verified. Multi-week resources are included only when their entire declared scope falls inside the selected weeks; partly overlapping sources are reported for review rather than silently extending the run.
