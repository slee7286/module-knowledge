# Scoped-generation verification

## Verified

- `.venv/bin/pytest -q --tb=short`: 98 passed.
- `sh -n scripts/machine-learning-weeks-1-5.sh`: exit 0.
- Real convenience-script preview against the local OneDrive clone: one module, Machine Learning; zero selected sources; one outside-week-scope file and five unassigned-week files; destination `Machine Learning/generated/runs/weeks-1-5`; run does not exist. The new material batch has not been supplied/mapped, so this is not a completeness verdict.
- Scratch-only synthetic generation with final implementation: six successful PDF compilations (question component, solution component, master; full and clean editions). Both master PDFs retain the literal question reference `source/data.csv`, including an exact line starting `Data source:`. Original PDF page assets are preserved and solution pages labelled. Earlier representative rendered contents/source/question pages were visually inspected for legibility and clipping; the final change affected only week-list parsing, not rendering.
- No actual Machine Learning generation, model inference, sync/upload, course-source edits, commits, or deletion of previous course outputs was performed.

## Independent review and regressions

First review reproduced output ancestor symlink escape, normalised module destination collisions, deletion of exact pedagogical paths by provenance stripping, lecture-number/week conflation, and truncated multi-week scope. All were reproduced in new failing tests, fixed, and included in the full suite.

Second review verified the original reproductions and additional sibling probes (output aliases/escapes, exact roles/rendering combinations, mapped legacy event numbering). It found an Oxford-comma week-list variant. Both reported variants were reproduced in failing tests and fixed by accepting an optional `and` after a comma. The final full suite and synthetic PDF build passed. That final one-line separator adjustment has regression coverage but was not independently re-reviewed; do not describe the complete final tree as independently approved.

## Runtime limits

The pinned Tectonic binary is installed and was exercised. The local Ollama `/api/tags` request failed with connection refused, and `ollama` was not found on PATH. Actual model-backed synthesis has therefore not been exercised or graded. Install/start the configured local backend and supply its default text/vision models (or select supported alternatives with the CLI) before generation. The new service/model guard rejects unavailable named synthesis runs before reserving output directories.

Source scope/dates require the user's explicit week labels or source-map.json. Missing inputs, official solutions, mathematical fidelity, and the future course PDFs still need source-linked review. The preview is inventory-only, not extraction or content validation.

See `docs/machine-learning-weeks-1-5.md` for staging and commands. Synthetic fixtures are temporary verification data under the Hermes scratch directory, not deliverable course notes.
