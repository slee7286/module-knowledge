# Feedback-learning verification

Executed from `/home/siheon/projects/module-knowledge`:

    .venv/bin/pytest -q --tb=short

Result: 104 passed in 4.35s.

The six new preference tests cover:

- global and module-specific preference injection into real drafting and consolidation HTTP request construction, using a controlled local HTTP server (two parameterised cases);
- changed preference instructions creating fresh draft and outline cache entries;
- a real synthetic tutorial generation preserving the selected rule snapshots and effective drafting prompt hash in its manifest (no PDF compilation or LLM inference required);
- malformed stage configuration failing explicitly;
- candidate/superseded/other-module/review-only rules excluded from presentation generation;
- explicitly configured missing registers failing rather than silently reverting.

A separate fresh Python process loaded the actual saved register: one drafting rule, two outline rules, two review rules, and two original user requests in the private history. This checks that the state can be reconstructed without conversational variables.

No source course files or existing note PDFs were changed by this implementation. No real LLM inference was performed; request wiring is verified, not improved note quality. Feedback ingestion/classification and preference promotion are agent-run steps on requested tasks, not an unattended service. Persistent entry points are `AGENTS.md` and the Hermes module-note skill; canonical state is the preference JSON plus its linked private edit history. Human review remains necessary for pedagogical/visual quality and source fidelity.
