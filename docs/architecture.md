# Module Knowledge — software design

Status: the local-first prototype renders source-linked LaTeX notes and now has an end-to-end Year 2 runner for discovery, bounded source snapshots, local drafting, individual lecture/tutorial documents, master-note assembly, and PDF compilation. The generated notes remain drafts requiring content and visual review. Separate EdStem/Panopto coverage remains unverified. See [the LaTeX workflow](latex-note-workflow.md) for active commands and limits.

## Goal, boundaries, and user controls

Build a local-first, per-module pipeline that accepts explicitly selected OneDrive files, EdStem threads, Panopto lecture video/audio, slides, lecture notes, tutorial questions and solutions, textbooks or permitted extracts, mock papers and marking schemes, and other declared documents. It should produce a comprehensive, source-linked set of notes plus separately generated mock tests and quizzes, but only on an explicit generation request. Never silently ingest an entire OneDrive account or publish/upload course material.

Each module has a user-approved configuration: module title, syllabus/learning outcomes, topic map, academic year/version, preferred notation, permitted source locations and cloud-processing policy, and output classification. The current explicit choice is LaTeX for Econometrics 1, Machine Learning, Microeconomics 2, and Corporate Finance and Capital Markets. The earlier DOCX-oriented proposal is superseded for these modules. The inspected Word exemplar is lecture-by-lecture and bullet-heavy, the TEX exemplar interleaves lectures and tutorials with mathematical notation, and the IPYNB exemplar combines extensive markdown, code and saved outputs. These observed structures should inform but not dictate other module styles.

## Pipeline and data contract

```text
User-approved OneDrive files / selected EdStem threads / Panopto assets / local files
  -> immutable source inventory + rights/processing policy
  -> format-specific extraction, with page/slide/time anchors
  -> canonical evidence blocks + quality flags
  -> module topic map and cheap lexical search
  -> topic-specific evidence retrieval and synthesis
  -> fact/coverage review -> canonical note sections
  -> LaTeX rendering for the four user-selected modules
  -> independent question bank -> quizzes and mocks + private answers/rubrics
```

1. Inventory first. Register every source with a stable ID, format, role (`lecture`, `slides`, `textbook`, `tutorial_problem`, `tutorial_solution`, `mock_problem`, `mock_solution`, `student_style_reference`, `discussion`, `other`), edition/version, SHA-256 of local bytes where applicable, permission level, and course/topic metadata. Store originals read-only in a private data root outside this project; never put licensed textbook pages or lecture recordings in Git. Detect duplicate files and revised versions. Exclude editor caches, Git internals, notebook checkpoints and personal feedback/journals by default. Record what could not be parsed rather than dropping it.
2. Extract by type. Prefer PDF/DOCX/PPTX/XLSX/LaTeX/IPYNB/Rmd/CSV and code structural parsers; preserve equations, tables, figures, code, speaker notes, formulas and page/slide/cell coordinates when present. Check text quality per page: several inspected solution PDFs have scanned or handwritten pages even when other pages are readable. OCR or visual analysis is a fallback for those pages, equations, diagrams, and inaccessible layouts; flag confidence and retain source crops for review. For Panopto video, prefer an authorized caption/transcript with timestamps and transcribe downloaded audio only when needed; align claims to timestamps and, where material depends on the screen or board rather than speech, inspect selected frames and correlate with slide pages. EdStem posts need course/thread/reply IDs, authorship and chronology. Public YouTube transcripts exist only for captioned videos.[4] Caption text alone is not a representation of diagrams or board work.[1]
3. Normalize into small evidence blocks, not a giant prompt. Suggested fields: `source_id`, immutable `source_version`, `source_type`, `locator` (page/slide/time/cell), `text`, `asset_refs`, `extraction_method`, `confidence`, `rights`, and `topic_ids`. Store manifest and extracted text/metadata in a private SQLite database with full-text search; keep source assets in files. Model summaries and embeddings are derived, versioned caches, never the sole evidence. Answerability depends on retrieving the underlying source block. Keep retrieved text explicitly untrusted as instructions.
4. Build a syllabus/topic coverage graph from the user's module outline and source structure. For each topic, gather the smallest sufficient evidence pack across lectures, slides, tutorial questions, solutions, and relevant textbook sections. Distinguish definitions, intuition, worked derivations, algorithms/code, misconceptions, and exam techniques. Record conflicts between lecturer notation, textbook conventions, and old exam solutions rather than silently reconciling them. Treat course materials as primary for assessed scope; textbook as explanation/extension with edition/page references.
5. Draft canonical sections from retrieved evidence. Each substantive claim, example, derivation, and exercise reference links back to exact source anchors (for instance slide 12, PDF page 87, video 00:23:14). A reviewer gate flags missing anchors, unsupported statements, omitted outcomes, inconsistent symbols, OCR uncertainty, and questions where the answer depends on an unavailable image. Solve derivations and sample computations independently where feasible. Do not treat the model's confidence as verification.
6. Render from a structured intermediate format, not from one monolithic model-generated DOCX or TEX. A canonical section has headings, prose, math AST/LaTeX, code blocks, figures, citations, worked examples, and review state. The active renderer builds LaTeX with stable lecture headings, exact locators, validated local inputs and compile checks. DOCX note generation is retired; legacy DOCX files may remain as read-only style or evaluation inputs. Create one source index and bibliography per module. Diff and rebuild only sections touched by changed sources or prompts; preserve explicit user edits through an overlay/review layer rather than overwriting files.
7. Create assessments as a separate workflow. Blueprint by syllabus outcome, difficulty, format, time allocation, and past-paper pattern. Generate novel variants rather than reproduce copyrighted questions verbatim by default; keep problem statements and private solutions/rubrics separate. Verify every answer against source evidence or an independent solver/test; for coding use unit tests, for numerical questions recomputation, for proofs human review. Check duplicates against prior papers and the generated bank, leakage of solution text into the question, ambiguity, and syllabus coverage. Export topic quizzes and timed mocks with marking schemes and source/explanation links. Require human approval before treating the bank as exam-ready.

## Token and cost discipline

- Extract text once and reuse it; cache by file hash + extractor version. Skip unmodified sources and unchanged topic sections on later runs. Deduplicate exact sources but retain provenance for all occurrences.
- Use cheap deterministic parsers, captions, OCR only where needed, SQLite FTS, and compact topic outlines before calling a model. Retrieval passes only relevant anchored snippets, not entire textbooks or long video transcripts. Chunk along headings, slide boundaries, and timestamped topic shifts; merge only when a cross-source section requires it.
- Escalate selectively: small/cheap model for classification and routine extraction checks; stronger model or multimodal reading for difficult mathematics, visual slides, contradictions, and final synthesis. Track input/output tokens, provider cost, cache hits, and quality per source and section. Set per-module budgets, stop thresholds, and a local-only option; measure quality before optimizing solely for cheapness.
- Use YouTube captions where available. Gemini Notebook (formerly NotebookLM) may be useful for interactive exploration: it accepts public captioned YouTube URLs and imports transcript text only, and can transcribe imported local audio. Its source limits and video restrictions make it an optional aid, not the authoritative extraction/traceability engine.[1] Do not route private university videos through a public YouTube workaround.
- Do not assume consumer Gemini Notebook has a programmable integration. Google documents a source-management API for the separate Gemini Notebook Enterprise product (preview, licensing/setup dependent); an enterprise adapter is optional only if the user's account, institutional policy and actual access permit it.[2] Otherwise use the documented UI manually for exploratory questions or rely on our own reproducible local pipeline. No browser scraping/undocumented API dependency.

## Permissions and privacy

Default to local processing. An upload to Google, YouTube, a cloud transcription/model provider, or an external service requires a per-module opt-in and confirmation that the university's permissions and source licences allow it. Avoid sharing complete textbook scans, paid content, personal data in recordings, or solutions outside authorized storage. Record the provenance and processing location of every derived artifact. Gemini Notebook's privacy terms vary with account type and feedback; verify the active account and university policy before making a cloud choice.[3] Public YouTube URLs should be used only when the videos are public and captioned; private recordings stay in approved storage.[1]

## Build phases and acceptance gates

A. Discovery and exemplar review: the four module output formats are specified, and an Econometrics 1 Lecture 1 draft is built from a frozen local source set. EdStem/Panopto coverage, rights policy, exact style-reference inspection and a measurable coverage rubric still need work.
B. Ingest prototype: implement manifest, versioning, extraction and source locators for a video, a slide deck, a problem/solution pair, and a textbook excerpt. Check an extracted sample against the originals, including an equation/figure and timestamp; no silent skips or uncited statements.
C. Single-topic pilot: produce one user-reviewed section in the chosen renderer and a small quiz. Evaluate correctness, completeness against topic outcomes, evidence links, formatting, and extraction failures. Compare cost/quality with and without optional Notebook assistance before adopting it.
D. One-module run: add change-aware builds, LaTeX compile/PDF review, question verification, a human review queue, and budget reporting. Do not claim comprehensive coverage unless the coverage matrix is complete or each gap is reported.
E. Multi-module hardening: regression fixtures for equations, OCR, diagrams, code, mixed editions, stale revisions, citations, marking schemes, and model/provider outages; portable export/restore and reproducibility checks.

## Decisions needed before implementation

- The first pilot is Econometrics 1 Lecture 1; next select frozen source manifests for Machine Learning, Microeconomics 2, and Corporate Finance and Capital Markets. The user-selected output format for all four is LaTeX.
- Provide the relevant EdStem course and Panopto lecture access paths or exports and confirm the permitted download/export scope; these collections have not yet been inventoried.
- Decide whether the material must remain entirely local or whether approved cloud services may receive selected sources. Identify any restricted recordings/textbooks and whether Notebook Enterprise is actually licensed, if that route matters.
- Set review expectations: is the default an editable draft pending your sign-off, or a publication-quality artifact requiring line-by-line human checking?

The current implementation includes reproducible LaTeX rendering and pinned local transcription tooling. The Econometrics 1 Lecture 1 note remains a draft; no claim of full-module coverage, quiz readiness, or mock-exam readiness is made.

## Sources

[1] https://support.google.com/notebooklm/answer/16215270?hl=en — Gemini Notebook source types and limits
[2] https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources — Gemini Notebook Enterprise source API
[3] https://support.google.com/notebooklm/answer/17004255?hl=en — Gemini Notebook privacy and terms
[4] https://support.google.com/youtube/answer/15930243?hl=en-GB — YouTube transcript availability
