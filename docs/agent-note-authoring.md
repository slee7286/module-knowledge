# Agent-authored notes and native source reproduction

This complements the automated CLI workflow. It documents the reusable acceptance checks used for privately authored notes; it does not make run-specific authoring scripts a generic CLI feature.

## Source-grounded authoring

- Read the preference register and private feedback history before drafting. Keep raw feedback and source excerpts outside the repository.
- Inventory exact module/week scope, freeze the selected sources and record input accounting. A problem-set number is not necessarily a teaching week. Treat folder dates as provisional unless corroborated by an authoritative schedule.
- Read both complete lecture transcripts when provided. Consolidate repetition, retaining unique explanations, examples, derivations, qualifications and disagreements.
- Preserve full questions and all subparts. Keep supplied written solutions, spoken lecturer answers and independently derived practice answers visibly distinct. Missing official solutions remain source gaps even when a practice answer is verified.
- Use a contents page, dated lecture/tutorial headings, topic subheadings and nested bullets. Concise phrasing must not reduce useful coverage.

## Native LaTeX instead of screenshots

When native reproduction is requested, reconstruct all reproduced source pages in scope, not only PDFs with a particular producer metadata tag.

1. Create one labelled, ordered source-page block per original page. Reproduce wording, equations, tables, code indentation, answer options and meaningful formatting structure as native LaTeX. Keep a page-level coverage ledger.
2. Inspect the actual source renders, especially raster code and poll options. Preserve faulty examples, duplicated or truncated options, typographic quotation marks and source scores. Put verified corrections outside the reproduced question. A zero poll score is not an answer key.
3. Extract original photographs/diagrams directly where possible. A cropped plot may remain an image; a full-page screenshot or screenshot of question/code text may not. Record source page, crop or image reference, and asset identity.
4. Clearly label reconstruction as reconstruction: absent original .tex files, do not claim original source was recovered or that the output is a pixel-identical facsimile.
5. Validate page/block count and order, source wording/numeric tokens, exact code literals/indentation, mathematical/table structure and selectable compiled text. Do not execute untrusted teaching code merely to check transcription.
6. Integrate into both component editions and combined notes, then check the final PDFs again. A standalone reconstruction passing does not prove the integrated edition preserved it. Check every embedded final image against the allowed genuine-figure assets; page-image preservation checks are not native-transcription checks.

## Final compilation and review

- Keep the previous reviewed run intact and create a fresh revision directory.
- Compile clean and full editions for lecture, tutorial and combined notes: six PDFs, three pairs. Keep citations/review flags in the full edition and check their absence from the clean edition.
- Use breakable, detokenised paths in citations. Give adjacent citations separate paragraphs if needed; split long inline code explanations at operation boundaries rather than shrinking all body text or changing supplied code.
- Inspect compiler warnings for both overfull boxes and missing glyphs. Under Tectonic, a legacy T1/lmodern preamble can drop literal Unicode curly quotes. A Unicode fontspec setup preserves those glyphs; upquote preserves straight verbatim apostrophes. Recheck selectable text after changing fonts.
- Recompute numerical examples and run independent checks on intentionally authored solution code. These checks do not prove general theorems or establish official answer authority.
- Inspect actual rendered covers, contents, equations, tables, figures, code, dense pages, transitions and final pages in all six PDFs. Record the review scope honestly; representative visual sampling is not an all-page visual review.
- Create a review queue with exact source locators and current physical PDF-page locations (cover = 1). Do not copy stale page numbers from an earlier run. Preserve source conflicts and missing-material decisions for human review.
- Close the run only after builds, coverage, mathematical/code checks, final-PDF content checks and rendered review are complete. Deliver exact paths and limitations.

## Permission gates

If the user asks to approve each successive week, persist a campaign record under the private module's generated directory. Authorise only the current week, finish and verify it, then stop and ask permission. Later weeks must remain unstarted; the original multi-week request is not blanket authorisation to continue past the gate.

## Boundary between repository and private runs

Publish reusable application code, regression tests and general procedures here. Keep original materials, notes, extracted text, course-specific transcriptions, private review histories and run-specific builders/verifiers in the private data tree. Those builders may import the reusable renderer, but the repository does not currently expose their native-transcription orchestration as a single automated command.
