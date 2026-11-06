# Reviewing the generated notes

## Which PDF to use

For each lecture, tutorial, and module master, use the `_FULL.pdf` version for review. It includes inline source citations, source-coverage gaps, and review flags. The corresponding PDF without a suffix is the clean reading copy: it keeps the note content but omits visible citations, source-review flags, and skipped-block details. Provenance remains in the `.evidence.json` sidecars under the module's `generated/` directory.

The clean PDF is not independently fact-checked. Do not use it as the only copy when checking correctness or completeness.

The notes use topic subheadings and nested bullets, following the Year 1 examples. Repeated points are consolidated within an event; exact repeated wording across later events becomes a “Previously covered” cross-reference. The cross-event pass only treats case/whitespace-identical points as repeats, so flag concepts that are repeated in different wording.

## Review pass

1. Start with the module's `*_MASTER_FULL.pdf` to check the overall structure, sequence, whether important topics are represented, and whether each “Previously covered” reference points to an earlier section that really contains the material.
2. Review each lecture/tutorial `*_FULL.pdf`. For a factual claim, definition, number, assumption, formula, or worked step, follow its citation and compare it with the cited page or slide.
3. Check every equation and diagram carefully: symbol definitions, signs, units, axis labels, curve direction, and whether the accompanying explanation matches the visual. Treat OCR/transcription and review flags as items to inspect, not as verified content. Resolve any `[unrendered ...]` placeholder in either edition against the cited source.
4. Read the full PDF's “Source coverage and review gaps” sections. Say whether each omitted block is unimportant, should be added, or needs a better interpretation. Check `Additional points` and any source-restored outline points for awkward or insufficiently organized material. When a model returns internal IDs as prose, the generator restores the corresponding input text rather than publishing IDs; those restorations still need topic/grouping review. Do not silently fill in a missing answer from general knowledge.
5. For tutorials, check that all questions, subparts, tables, figures and provided solutions are present and that questions remain distinct from answers. PDF tutorial pages are reproduced without rewriting; compare them with the originals, including the pages labelled as provided official solutions. DOCX handouts/code are extracted separately, so check drawings, equations and list structure against the DOCX. If no solution is supplied, record that gap; do not treat a question-only sheet as answered.
6. After source checks, use the unsuffixed PDFs as the clean reading copies. Report any wording that is unclear, too compressed, repeated in different wording, or needs more explanation.

## Persistent learning from feedback

Every requested edit is preserved in the private history linked by `config/note-preferences.json`, with its original wording, scope, outcome and verification evidence. Explicit reusable preferences update that register for future notes; one-off factual corrections stay local and uncertain patterns remain candidates. Read [the feedback-learning procedure](feedback-learning.md) for the restartable workflow. The agent maintains these records, not the reviewer.

## How to send corrections or interpretation

For all note revisions, only three fields are required. Write the suggested change in ordinary human sentences; no special syntax or replacement LaTeX is necessary. Send entries in a text file or paste them into chat, one issue per entry:

```text
File: Machine_Learning_Week_1.pdf
Page: 6
Suggested change: Explain the difference between training loss and expected loss more clearly, with a small example.
```

The page is the physical PDF page, counting the cover as page 1. Either the clean or full edition is accepted; use the filename of the edition actually reviewed. If using a printed page label instead, saying so is enough. For document-wide changes, use `Page: all`.

Quotes, section headings, source citations, reasons, confidence labels and exact replacement wording are optional, not prerequisites. The agent must inspect the specified PDF page, locate the corresponding editable source, retrieve supporting course material when needed, and translate the natural-language request into the appropriate content or layout edit. Ask a targeted clarification only when the page and sentence leave a material ambiguity or when a factual correction conflicts with available evidence; do not demand the longer form by default. Keep user interpretations distinct from source-supported facts and do not invent evidence.

Apply each accepted change to the shared editable content or template, not directly to a PDF. Update a deterministic body-authoring script too when it would otherwise overwrite the correction. Rebuild both editions and affected combined/master notes, rerun relevant checks, and visually inspect affected pages. Preserve the reviewed version or its page mapping before rebuilding so remaining feedback continues to refer to the original pages. Record the result of each requested change, including anything blocked or needing clarification.

Partial review batches are welcome. An instruction such as “apply this feedback” authorises the revision batch; writing feedback alone does not trigger automatic monitoring or edits.
