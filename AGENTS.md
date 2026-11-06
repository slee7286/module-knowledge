# Course-note generation and revisions

Before any note authoring, generation or revision task:

1. Read `docs/feedback-learning.md` and `docs/note-review-guide.md`.
2. Read `config/note-preferences.json` (or `MODULE_KNOWLEDGE_PREFERENCES` when set), then read its `feedback_history` and the relevant past edits. These files, not chat context, are the durable preference state.
3. Apply active preferences with the appropriate scope. Keep candidate/superseded preferences out of generation. Current explicit user directions take precedence; preserve superseded-rule history.

For feedback, accept only File, Page and Suggested change in ordinary human sentences. Do the source tracing and technical translation yourself. Record every original suggestion before editing, append its implementation/verification outcome afterward, and promote reusable preferences according to the feedback-learning guide. Do not generalise one-off factual corrections into global style rules.

Edit shared source and any deterministic authoring script, not PDFs. Rebuild both editions and affected masters, verify relevant tests and affected rendered pages, and preserve reviewed versions/page mappings. Source course materials are read-only. Keep private course content and detailed review evidence outside this project; use the private history path in the preference register.

Do not claim that updating preferences retrains a model or guarantees future quality. The generation pipeline reads active presentation rules into its prompts; agents must apply review/workflow rules and actual renderer changes separately. Do not edit the register during a running generation; use a fresh run after updates.
