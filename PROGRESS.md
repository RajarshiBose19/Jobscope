# JobScope — Progress Log

> Hand-maintained. Append at the top after each session. Keep entries
> short and concrete — what changed, what's next, what's blocking.

## Phase status snapshot

| Phase | Status |
|---|---|
| 0. Brainstorming & design | **COMPLETE** 2026-05-25 |
| 1. Implementation plan (writing-plans skill) | **NEXT** |
| 2. Foundations: package skeleton, .env, config, DuckDB schema, seed_skills | pending |
| 3. Profile pipeline: jet_parse resume → profile.json → user_skills | pending |
| 4. Scraper: browser, login, search, listing, extract — copied + adapted from reference | pending |
| 5. AI: prompts, Pydantic schema, analyzer with retry + key rotation | pending |
| 6. State + decision: current_job.json snapshot + tkinter popup | pending |
| 7. Orchestrator: end-to-end loop wired together | pending |
| 8. Live canvas: 8 frames + refresh scripts | pending |
| 9. Historical canvas: 4 charts + refresh scripts | pending |
| 10. Jetro skill file (`.jetro/skills/jobscope_dashboard.md`) | pending |
| 11. Tests + fixtures | pending |
| 12. Deploy historical dashboard + LDF publish | pending |
| 13. Demo recording + smoke on clean machine | pending |

## Log (newest first)

### 2026-05-25 — Brainstorming and design approved

- Read brief, AGENT.md, reference repo structure (`auto_job_applier_linkedIn/`).
- Locked in 7 architecture decisions through clarifying questions. See PROJECT.md table.
- Wrote design spec: `docs/superpowers/specs/2026-05-25-jobscope-design.md`.
- Wrote PROJECT.md (onboarding index) and PROGRESS.md (this file).
- **Next:** invoke the `superpowers:writing-plans` skill to turn the design into
  an executable implementation plan.

## Open blockers / risks under watch

- LinkedIn anti-bot — high risk for demo day; mitigation in spec §9
- Gemini schema enforcement on Flash Lite — verify on first end-to-end run
- DuckDB read/write contention under refresh load — should be OK with read-only conns; check during phase 8

## Notes from the user worth preserving

- "selenium only is preferable" — no paste-JD fallback
- "lets just have the data be shown in jetro" — canvas is read-only; decisions in popup
- "use as much configuration related stuff from auto_job_applier_linkedIn" — but copy code, do NOT import; reference repo will be deleted later
- "the way they extract shit from linkedin we can use" — lift selectors and patterns from `runAiBot.py`
