# JobScope

A LinkedIn job-market intelligence tool built on [Jetro](https://jetro.ai). A Selenium scraper iterates job listings, sends each JD to Gemini for structured analysis, writes results into DuckDB, and renders a live cockpit + historical dashboard on a Jetro project canvas. Decisions (Apply / Skip / Bookmark) happen through a tkinter popup — the canvas is strictly read-only.

**It is not an auto-applier. It never clicks Apply.**

---

## How It Works

```
LinkedIn Job Feed
      |
      v
Selenium Scraper  (undetected-chromedriver)
      |
      v
Pre-Filter Pipeline ──────────────> auto-skip ~40-60% of listings
(applied badge, blacklist,            before any Gemini API cost
 experience ceiling, bad-word scan,
 recent-analysis check)
      |
      v
Gemini 2.5 Flash Lite  (3-key rotation)
      |
      +──────────────+──────────────+
      |              |              |
      v              v              v
   DuckDB    current_job.json   Tkinter Popup
  (8 tables,   (atomic swap)   (Apply / Skip /
   4 views)         |            Bookmark)
      |              |
      v              v
 Historical      Live Cockpit
 Dashboard        (9 frames)
 (4 frames)       polls @ 2s
 polls @ 30s
      |              |
      +──────────────+
             |
   Jetro Project Canvas  (13 frames total)
```

---

## Requirements

- Python 3.11+
- Google Chrome (recent stable)
- [Jetro VS Code extension](https://jetro.ai) — required for the canvas dashboard
- LinkedIn account
- Gemini API key(s) — free tier works, get one at https://aistudio.google.com/app/apikey

---

## Setup

**1. Clone and install**
```bash
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

**2. Configure secrets**

Copy `.env.example` to `.env` and fill in:
```
LINKEDIN_USERNAME=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password
GEMINI_API_KEYS=key1,key2,key3
```
Three Gemini keys are recommended for key rotation on rate limits — one works fine for light use.

**3. Set your profile**

Edit `projects/jobscope/profile.json` with your details (name, experience, skills, CTC expectations). This is the candidate source of truth that Gemini scores every job against.

Place your resume PDF at `projects/jobscope/resume.pdf`.

**4. Edit search config**

Open `jobscope/config.py` and update:
- `SEARCH_TERMS` — the roles you're searching for
- `SEARCH_LOCATION` — your target city
- `BLACKLISTED_COMPANIES` — companies to auto-skip

**5. One-time setup**
```bash
python -m jobscope seed-skills     # Load canonical skill registry
python -m jobscope parse-resume    # Parse resume PDF, sync profile to DB
```

**6. Open Jetro**

Open this folder in VS Code with the Jetro extension. The project canvas (`projects/jobscope`) will have 13 frames — 9 live cockpit frames and 4 historical charts. Refresh bindings auto-attach on first render.

**7. Run**
```bash
python -m jobscope run
```

Chrome opens, logs into LinkedIn, and starts iterating your saved searches. A tkinter popup appears after each job analysis with the fit score and Gemini's recommendation — you pick Apply, Skip, or Bookmark.

---

## CLI Commands

| Command | What it does |
|---|---|
| `python -m jobscope run` | Start the scraper + analyzer + decision loop |
| `python -m jobscope login-only` | Open Chrome and log in only — useful for pre-clearing captcha walls before a demo |
| `python -m jobscope parse-resume` | Parse resume PDF and sync profile.json to DB |
| `python -m jobscope seed-skills` | (Re)load canonical skill registry from CSV |
| `python -m jobscope clear-live` | Reset current_job.json to idle state |
| `python -m jobscope reset --confirm` | Archive DB to `.bak-{ts}`, recreate empty schema |
| `python -m jobscope backfill-salary` | Re-parse salary data from existing JD text |

---

## Canvas Frames

**Live cockpit** (updates every 2s from `current_job.json`):

| Frame | What it shows |
|---|---|
| Bot Status | Staleness indicator (live / slow / stalled), last 3 warnings |
| Current Job | Title, company, location, work style, posted date |
| Fit Gauge | Score 0–100 with green / yellow / red coding |
| Skills | Required vs nice-to-have, each tagged matched / partial / missing |
| Experience | Verdict (in range / under / over) with year comparison |
| Red Flags | Flagged concerns with evidence snippets from the JD |
| Recommendation | Gemini's recommendation + action required flag |
| Resume Tailoring | Per-job suggestions on what to adjust in your resume |
| Session KPIs | Running totals — evaluated, applied, skipped, avg fit |

**Historical dashboard** (updates every 30s from DuckDB aggregates):

| Frame | What it shows |
|---|---|
| Skill Gaps | Top missing skills ranked by demand frequency |
| Fit Distribution | Histogram of fit scores across all evaluated jobs |
| Salary Map | Salary ranges by search term |
| Search Terms | Avg fit, apply rate, job count per search term |

---

## Project Layout

```
jobscope/
├── orchestrator.py     # Main bot loop
├── config.py           # All constants + env loading
├── cli.py              # Click CLI entry points
├── ai/
│   ├── prompts.py      # Gemini system + user prompt templates
│   ├── schema.py       # Pydantic models for structured AI output
│   ├── client.py       # GeminiClient with 3-key rotation
│   └── analyzer.py     # Orchestrates Gemini call + validation
├── scraper/
│   ├── browser.py      # Chrome driver setup (undetected-chromedriver)
│   ├── login.py        # LinkedIn login + captcha detection
│   ├── search.py       # Search URL builder + navigation
│   ├── listing.py      # Job card pagination + iteration
│   ├── extract.py      # JD text, experience, salary extraction
│   ├── apply.py        # Apply / Save button interactions
│   └── applied_detector.py  # Auto-detect already-applied jobs
├── db/
│   ├── schema.sql      # 8-table DuckDB schema
│   ├── views.sql       # 4 analytical views
│   ├── connection.py   # Connection factories (rw / ro)
│   └── repo.py         # All DB read/write operations
├── decision/
│   └── popup.py        # Tkinter decision / confirmation dialogs
├── state/
│   └── snapshot.py     # Atomic current_job.json read/write
├── profile/
│   ├── parse_resume.py # PDF text extraction
│   └── normalize.py    # Profile loading + DB sync
└── utils/
    ├── logging.py      # Structured JSONL logging
    └── ids.py          # UUID + session ID generation

.jetro/
├── frames/             # 13 HTML canvas frames
├── scripts/            # 6 Python refresh-binding scripts
└── skills/
    └── jobscope_dashboard.md  # Custom Jetro skill

tests/                  # 40 pytest tests + LinkedIn HTML fixtures
projects/jobscope/      # Jetro project canvas state + profile.json
```

---

## Notes

- **Anti-bot**: Uses `undetected-chromedriver` and a persistent Chrome profile. Run `login-only` before a demo session to pre-clear any captcha walls.
- **DuckDB concurrency**: The scraper holds one read-write connection. Refresh scripts use separate read-only connections — safe with DuckDB ≥1.0.
- **Jetro dependency**: The canvas dashboard only works inside the Jetro VS Code extension. The scraper, DB, and AI pipeline run independently without it.
- **Cost**: Gemini 2.5 Flash Lite is ~$0.0003 per job analysis. The pre-filter pipeline skips ~40–60% of listings before any API call.
