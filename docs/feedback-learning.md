# Durable feedback learning for course notes

## Durable state and restart

- `config/note-preferences.json` is the canonical register of reusable preferences. The private edit history is the `feedback_history` path in that file (currently `/home/siheon/projects/OneDrive/note-feedback/edits.json`). Do not move raw course excerpts into this project.
- At the beginning of EVERY note-generation or note-revision task, read this guide, the current register and the relevant history entries. Do not rely on chat memory. `AGENTS.md` is the entry point for agents outside Hermes; the persistent module-note skill carries the same startup rule for Hermes.
- For migration, copy the project AND the private history; update `feedback_history` and the history's `preference_register` locator. `MODULE_KNOWLEDGE_PREFERENCES` can point the CLI to another preference register. An explicitly configured missing/malformed register is an error, not permission to forget preferences.
- Nothing monitors feedback files automatically. On a requested review/revision or generation task, the agent maintains these files. This changes saved instructions and generation inputs, not model weights.

## Repeatable revision loop

1. Accept File, Page and Suggested change, with normal human sentences. Page means the physical PDF page by default; `all` means document-wide. Extra source citations and exact replacement text are optional.
2. BEFORE editing, append each original suggestion to the private history with a unique ID, file, page, untouched suggested text, classification, scope, status `received`, optional linked preference IDs, and an `events` array. Save pasted-chat suggestions too. Preserve the reviewed PDF or an unambiguous version/page mapping so later comments remain locatable.
3. Inspect the specified page and trace it to the editable body, source materials and any authoring script. Record the interpretation and source check in a new event. Classify the request:
   - one-off factual/content correction: fix the affected material; do not generalise its answer to other topics;
   - explicit reusable preference: record the rule with its actual scope (`all` or an exact module name);
   - possible pattern: record a `candidate`, with supporting feedback IDs; do not inject it as an active preference merely because one page needed a change;
   - ambiguous/conflicting evidence: mark `needs_clarification` or `blocked`, explain precisely, and ask only the necessary question.
4. For explicit general preferences, create or update an `active` rule before the next relevant generation. For inferred patterns, retain candidate status until confirmed or supported clearly by repeated feedback; ask about scope when it materially changes other notes. Keep latest explicit user directions above older preferences. Mark an older conflicting rule `superseded` and retain its history/link to the replacement instead of silently deleting it. Never let style preferences erase useful coverage, alter original questions or invent official answers.
5. Apply accepted changes to shared source/templates and any deterministic authoring code that could overwrite them. Rebuild both editions and affected masters. Run relevant mathematical/code checks and inspect the affected compiled pages. Add an event with changed artifact locations, verification results, and a disposition of `applied`, `blocked`, `needs_clarification`, or `declined` (with reason). Do not label an unverified edit as applied.
6. At the end of the batch, give a short summary of applied/outstanding edits and new or changed reusable preferences. The user should not have to write the ledger or maintain the register.

## Token-efficient revisions

Start from the last verified editable sources and the feedback delta. Patch only affected fragments; reuse unchanged transcriptions, assets, coverage ledgers and verified content. Read relevant source ranges rather than reloading entire transcripts. Recompile dependent PDFs for pagination and contents without sending unchanged prose through model generation again.

Reuse a compiled artifact only when its relevant inputs and checks are still valid. A newly discovered rendering defect can require recompilation even when its content is unchanged; record that exception instead of claiming the artifact was reusable. Inspect changed pages and affected layout boundaries, retain cheap global integrity checks, and record changed versus reused sections. Do not invent token-savings percentages or describe this procedure as an automatic dependency cache.

## Preference register contract

The JSON root has `version: 1` and a `rules` list. Each rule has:

- `id`: stable descriptive identifier;
- `status`: `active`, `candidate`, `superseded` or `retired`;
- `scope`: `all` or an exact module name;
- `stages`: any of `draft`, `outline`, `review`;
- `instruction`: the general rule, not a copy of course answers;
- `feedback_ids`: the original suggestions that support it;
- optional origin, rationale, exceptions, replacement links and verification notes.

Existing standing style rules are seeded with an explicit baseline origin, not fabricated user feedback. The private history preserves original requests and their dispositions; page-level corrections remain distinct from reusable presentation rules.

## How future generation uses the register

`module_knowledge.preferences.preference_context` loads active, stage-matching, scope-matching rules at runtime. `draft_slice` appends them to the evidence-grounded drafting prompt; `_request_outline` appends them to the consolidation prompt. The regular generator passes the module name and records the selected rules and effective prompt hashes in each note manifest under `processing.note_preferences`. Request/cache keys include the effective prompt, so changing a rule changes the model-request cache key. Review-only rules are not injected into note prose or confused with course evidence.

Agent-authored notes must also read and follow the register before authoring. Typography/layout preferences require an actual template or renderer change and a rebuild; storing a rule alone is not proof of implementation. Add regression tests when a preference is enforceable in code; use rendered-page review for visual and pedagogical preferences that cannot be reduced to a text assertion.

Do not change the register during a running generation. Finish or stop that run, update preferences, then start a fresh named run so all notes and recorded prompt metadata use a consistent policy. Earlier PDFs are not regenerated merely because the register changes; revise them only in an authorised batch.

## Verification

From the project root:

    .venv/bin/pytest tests/test_note_preferences.py -q
    .venv/bin/pytest -q

Integration tests use a deliberately controlled local HTTP test server, not an actual LLM. They verify request wiring and provenance, not that a language model will obey every preference. Human review remains the measure of whether future notes actually fit better.
