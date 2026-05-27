# JobScope — Progress Log

> Hand-maintained. Append at the top after each session. Keep entries
> short and concrete — what changed, what's next, what's blocking.

## Phase status snapshot

| Phase | Status |
|---|---|
| 0. Brainstorming & design | **COMPLETE** 2026-05-25 |
| 1. Implementation plan (writing-plans skill) | **COMPLETE** 2026-05-25 |
| 2. Foundations: package skeleton, .env, config, DuckDB schema, seed_skills | **COMPLETE** 2026-05-27 |
| 3. Profile pipeline: resume PDF → profile.json → user_skills | **COMPLETE** 2026-05-27 |
| 4. Scraper: browser, login, search, listing, extract | **COMPLETE** 2026-05-27 (import smoke only — no live LinkedIn run yet) |
| 5. AI: prompts, Pydantic schema, analyzer with retry + key rotation | **COMPLETE** 2026-05-27 |
| 6. State + decision: current_job.json snapshot + tkinter popup | **COMPLETE** 2026-05-27 |
| 7. Orchestrator: end-to-end loop wired together | **COMPLETE** 2026-05-27 (CLI verified end-to-end; full bot run not yet exercised) |
| 8. Live canvas: 9 frames + refresh scripts | **COMPLETE** 2026-05-27 |
| 9. Historical canvas: 4 charts + refresh scripts | **COMPLETE** 2026-05-27 (waiting on real data) |
| 10. Jetro skill file (`.jetro/skills/jobscope_dashboard.md`) | **COMPLETE** 2026-05-27 |
| 11. Tests + fixtures | **COMPLETE** 2026-05-27 (40 passing) |
| 12. Deploy historical dashboard + LDF publish | **PENDING** (user-side after first real run) |
| 13. Demo recording + smoke on clean machine | **PENDING** (user) |

## Canvas state

A project canvas was auto-created on first `jet_render` to `projectSlug: jobscope`:

- **Canvas id:** `jobscope_canvas_mpo9rbl5`
- **Name:** "Jobscope Canvas"

All 13 frames are rendered on this single canvas with refresh bindings active.
Layout: live frames in the top half (y=0 → y=860), historical charts in the bottom half (y=1080 → y=1700+).

### Frame element IDs (for reference if you need to move/resize)

Live cockpit:
- `mcp-1779899206770-3` — Bot Status (binding: refresh_current_job.py @ 2s)
- `mcp-1779899211588-4` — Current Job (binding: refresh_current_job.py @ 2s)
- `mcp-1779899216448-5` — Fit Score (binding: refresh_current_job.py @ 2s)
- `mcp-1779899221150-6` — Experience match (binding: refresh_current_job.py @ 2s)
- `mcp-1779899226837-7` — Red flags (binding: refresh_current_job.py @ 2s)
- `mcp-1779899231806-8` — Skills breakdown (binding: refresh_current_job.py @ 2s)
- `mcp-1779899237050-9` — AI recommendation (binding: refresh_current_job.py @ 2s)
- `mcp-1779899243375-10` — Resume tailoring (binding: refresh_current_job.py @ 2s)
- `mcp-1779899248895-11` — Session KPIs (binding: refresh_session_kpis.py @ 5s)

Historical:
- `mcp-1779899253649-12` — Skill gaps (binding: refresh_skill_gaps.py @ 30s)
- `mcp-1779899258687-13` — Fit distribution (binding: refresh_fit_distribution.py @ 30s)
- `mcp-1779899263602-14` — Salary map (binding: refresh_salary_map.py @ 30s)
- `mcp-1779899268529-15` — Search term report (binding: refresh_search_term_report.py @ 30s)

**Note 2026-05-27 (post-MVP fix):** Initial bulk render call had all 13 `jet_render` invocations in parallel, which triggered a race condition in Jetro's canvas-file persist layer — the calls returned success IDs but nothing actually landed on disk. Fixed by re-rendering each frame sequentially. Lesson: `jet_render` to the same canvas is not parallel-safe; serialize them.

## Architectural deviation from spec

The spec called for **two** canvases (Live + Historical) plus **C2 fan-out** in the live canvas (one hub → 8 subscribers via `__JET.send` / `__JET.on`). At implementation time we discovered:

1. The `jet_canvas` MCP tool doesn't expose `enableC2`, `addWire`, or any canvas-creation action — canvases are auto-created from `jet_render` calls. Multiple canvases per project isn't reachable via MCP.
2. Without `enableC2` + `addWire` we couldn't establish the C2 channel, so the subscriber-frame `__JET.on('current_job', ...)` listeners would never fire.

**Pivot taken:** single canvas, all 13 frames laid out by Y position. Each live subscriber frame got its own direct refresh binding to `refresh_current_job.py` (2s interval), and the frame JS was edited to listen on `jet:refresh` instead of `__JET.on`. Slightly redundant (8 frames each polling the same tiny JSON every 2s) but it works, and the JSON read is cheap (sub-millisecond).

The `live_hub.html` file is committed but unused on the canvas — left in tree as documentation.

## Open next steps for the user

1. **First live run (smoke):** `python -m jobscope run` — confirm Chrome opens, LinkedIn login succeeds, first job analyzes, tkinter popup appears, canvas updates within ~3s of decisions. Fix any DOM-drift surprises in `jobscope/scraper/extract.py` selectors against the real current LinkedIn DOM.
2. **Seed historical data:** run the bot for ~30 min to accumulate 50+ evaluated jobs across all 5 search terms. The four historical charts populate from this.
3. **Deploy:** `jet_skill({ name: "Deploy App" })` then `jet_deploy({ action: 'start', projectSlug: 'jobscope', canvasId: 'jobscope_canvas_mpo9rbl5' })` for a public URL.
4. **Publish LDF:** `jet_skill({ name: "Publish LDF" })` then `jet_doc` to publish a downloadable artifact.
5. **Demo recording:** 5-minute walkthrough — VS Code with canvas open, run bot, show analyses landing, show historical aggregates, show the deployed URL.
6. **Delete reference repo:** once you're confident `jobscope/` is self-contained, `rm -rf auto_job_applier_linkedIn` and commit. (Add `.jetro/credentials/` and other `.jetro/*` runtime subdirs to `.gitignore` before this commit — currently only `.jetro/cache/` and `.jetro/output/` are ignored.)

## Log (newest first)

### 2026-05-27 — MVP implementation complete

Built all 13 Jetro frames + 6 refresh scripts + the canvas wiring on one project canvas (`jobscope_canvas_mpo9rbl5`). Architectural pivot: dropped C2 fan-out in favor of direct per-frame refresh bindings — MCP didn't expose C2 actions. Everything else from Phases 2-11 implemented, 40 tests passing, README + Jetro skill shipped. Open work is all user-side: actual live bot run, seeded historical data, deploy, demo recording, reference-repo deletion. See "Open next steps" above.

### 2026-05-25 — Brainstorming and design approved

- Read brief, AGENT.md, reference repo structure (`auto_job_applier_linkedIn/`).
- Locked in 7 architecture decisions through clarifying questions. See PROJECT.md table.
- Wrote design spec: `docs/superpowers/specs/2026-05-25-jobscope-design.md`.
- Wrote PROJECT.md (onboarding index) and PROGRESS.md (this file).

## Open blockers / risks under watch

- LinkedIn anti-bot — high risk for demo day; mitigation: `stealth_mode=True`, `login-only` CLI to pre-clear captcha walls before a demo, the orchestrator's `_wait_for_user_verify` tkinter popup
- Gemini schema enforcement on Flash Lite — verify on first end-to-end run; analyzer has 1 retry + key rotation if it misbehaves
- LinkedIn DOM drift — first live run is the real test of `jobscope/scraper/extract.py` selectors
- DuckDB read/write contention — should be OK with read-only conns; check during first multi-job session
- `.jetro/` subdirs other than `frames/scripts/skills/` are NOT gitignored — `.jetro/credentials/` particularly could leak. Broaden the ignore before next public commit.

## Notes from the user worth preserving

- "selenium only is preferable" — no paste-JD fallback
- "lets just have the data be shown in jetro" — canvas is read-only; decisions in popup
- "use as much configuration related stuff from auto_job_applier_linkedIn" — but copy code, do NOT import; reference repo will be deleted later
- "the way they extract shit from linkedin we can use" — lift selectors and patterns from `runAiBot.py`
- "Honestly dont wanna read all that. I hope you followed our brainstorming session properly" — user trusts the spec/plan and wants execution, not progress reports
