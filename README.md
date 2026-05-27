# JobScope

Personal LinkedIn job-market intelligence — a Selenium scraper that calls
Gemini per job description, writes to DuckDB, and renders a live cockpit and
historical dashboard on Jetro canvases. Decisions happen via a tkinter popup.
**It never clicks Apply.**

Built as a Round 2 submission for Berrywise (berrywise.ai).

## Quick start

1. Install Python 3.11+ and Chrome (any recent stable).
2. Clone, create a venv, install:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   ```
3. Copy `.env.example` to `.env` and fill in:
   - `LINKEDIN_USERNAME`, `LINKEDIN_PASSWORD`
   - `GEMINI_API_KEYS` — comma-separated. Get free keys at https://aistudio.google.com/app/apikey
4. One-time setup:
   ```powershell
   python -m jobscope seed-skills
   python -m jobscope parse-resume
   ```
5. Open this folder in VS Code with the Jetro extension. Open the **Live
   Cockpit** and **Historical Dashboard** canvases under projects/jobscope.
6. Start the bot:
   ```powershell
   python -m jobscope run
   ```
   A Chrome window opens, logs into LinkedIn, runs your saved searches, and
   pops up a tkinter dialog after analyzing each job.

## Commands

| Command | What it does |
|---|---|
| `python -m jobscope run` | Start the scraper + analyzer + popup loop |
| `python -m jobscope clear-live` | Reset `current_job.json` to idle |
| `python -m jobscope reset --confirm` | Archive DB to `.bak-{ts}`, recreate empty tables |
| `python -m jobscope seed-skills` | (Re)load canonical skill registry from CSV |
| `python -m jobscope parse-resume` | Verify resume PDF parses; sync profile.json to DB |
| `python -m jobscope login-only` | Open Chrome, log into LinkedIn, then close — useful for clearing captcha walls |

## Configuration

Constants live in `jobscope/config.py`. Secrets in `.env`. Edit `config.py`
to change search terms, location, filters, refresh intervals, etc.

The candidate profile is in `projects/jobscope/profile.json` and is the
source of truth — re-run `python -m jobscope parse-resume` to sync.

## Project layout

See `PROJECT.md` for the full repo index. Key entry points:
- `jobscope/orchestrator.py` — main bot loop
- `jobscope/db/schema.sql` — DuckDB schema
- `jobscope/ai/prompts.py` — Gemini prompt
- `.jetro/frames/` — canvas HTML
- `.jetro/scripts/` — canvas refresh scripts
- `.jetro/skills/jobscope_dashboard.md` — Jetro skill for building more dashboards
- `docs/superpowers/specs/2026-05-25-jobscope-design.md` — full design spec
