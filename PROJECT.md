# JobScope — Project Index

> **For any future session reading this:** start here. This file is the map.
> It is hand-maintained (NOT auto-generated). Keep it accurate when scope changes.

## What this is

**JobScope** is a personal LinkedIn job-market intelligence tool built on Jetro,
being built as a Round 2 submission for a Backend Developer role at
**Berrywise** (berrywise.ai).

A Selenium scraper iterates LinkedIn job listings, sends each JD to Gemini for
analysis, writes results into DuckDB, and renders live + historical
intelligence on Jetro canvases. A tkinter popup in the Python tool handles
Apply/Skip/Bookmark decisions — the canvas is read-only.

**It is NOT an auto-applier.** It never clicks Apply.

## Read in this order

1. `jobscope_final_brief.md` — original brief from the user; the WHY
2. `docs/superpowers/specs/2026-05-25-jobscope-design.md` — approved design; the WHAT and HOW
3. `PROGRESS.md` — current phase, what's done, what's next
4. `CLAUDE.md` — Jetro platform context (auto-generated, do NOT edit)
5. `auto_job_applier_linkedIn/` — reference repo we are mining for LinkedIn DOM selectors, login flow, and Gemini patterns. **Will be deleted post-MVP. Do not import from it — copy code into `jobscope/` and adapt.**

## Repo layout (current + planned)

| Path | Status | Purpose |
|---|---|---|
| `jobscope_final_brief.md` | exists | The product brief from the user |
| `CLAUDE.md`, `AGENT.md` | exists | Jetro platform context (auto-generated) |
| `auto_job_applier_linkedIn/` | exists (read-only) | Reference code donor; will be deleted post-MVP |
| `docs/superpowers/specs/2026-05-25-jobscope-design.md` | exists | Approved design spec |
| `PROJECT.md` | this file | Onboarding index |
| `PROGRESS.md` | exists | Phase/status tracker |
| `jobscope/` | **planned** | The Python package — scraper, AI, DB, orchestrator |
| `projects/jobscope/` | exists (empty) | Jetro project canvas + state files |
| `projects/jobscope/jobscope.duckdb` | planned, gitignored | The DuckDB database |
| `projects/jobscope/profile.json` | planned, committed | Candidate profile (source of truth) |
| `projects/jobscope/resume.pdf` | planned, copy from reference | Resume PDF |
| `projects/jobscope/state/current_job.json` | planned, gitignored | Live snapshot file |
| `.jetro/frames/` | planned | 12 HTML frames (8 live + 4 historical) |
| `.jetro/scripts/` | planned | 6 refresh-binding scripts |
| `.jetro/skills/jobscope_dashboard.md` | planned | A Jetro skill shipped with the project |
| `tests/` | planned | pytest tests + LinkedIn HTML fixtures |
| `logs/jobscope.log` | planned, gitignored | Structured JSONL log |
| `.env` | planned, gitignored | LINKEDIN_USERNAME, LINKEDIN_PASSWORD, GEMINI_API_KEYS |
| `.env.example` | planned, committed | Template for `.env` |
| `pyproject.toml` | planned | Python deps |

## Locked-in decisions (do not relitigate without good reason)

| Decision | Value | Why |
|---|---|---|
| Scope | Lean MVP + per-job resume tailoring | 1-week deadline |
| JD source | Selenium primary, full commitment | User chose; matches brief; no paste fallback |
| Scraper ↔ canvas | One-way only (scraper writes, canvas reads) | Sub-100ms decisions; no bidirectional state machine |
| Decisions | tkinter popup in Python | Brief says "dialog prompts or terminal input"; tkinter is more demo-friendly |
| Canvas split | Two canvases (live + historical) | Different refresh models |
| AI | Gemini 2.5 Flash Lite, 3-key rotation | Cheap, fast, brief specifies Gemini |
| Reference repo | Copy code, do NOT import | User will delete `auto_job_applier_linkedIn/` post-MVP |
| Config | `jobscope/config.py` (constants) + `.env` (secrets) | Self-contained; reference is donor only |
| Live data channel | `current_job.json` file (atomic write) | No DuckDB contention on live path |
| Profile source | `jet_parse` resume PDF → `profile.json` | Showcases jet_parse; profile.json is editable truth |
| DuckDB version | ≥ 1.0 | Concurrent read-only connections require this |

## Out of scope for MVP (schema-ready for later)

Talking points generator · Interview prep seeds · Response tracking ·
Skill adjacency · Learning priorities · Company watchlist · Application funnel ·
Weekly trends · Bookmark resurfacing UI

## How sessions hand off to each other

- **Always update `PROGRESS.md`** at the end of any work session
- Never edit `CLAUDE.md` (auto-overwritten)
- Never edit `auto_job_applier_linkedIn/` (read-only reference)
- Major spec changes → bump `docs/superpowers/specs/2026-05-25-jobscope-design.md` and note in PROGRESS.md
- Memory snippets the user has saved live in `memory/` at the Claude config root
