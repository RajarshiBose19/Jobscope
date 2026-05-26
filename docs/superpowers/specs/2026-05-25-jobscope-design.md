---
title: JobScope — Design
date: 2026-05-25
status: APPROVED
owner: Rajarshi Bose
scope: MVP for Berrywise Round 2 submission
related:
  - ../../../jobscope_final_brief.md      # source brief
  - ../../../PROJECT.md                   # repo onboarding index
  - ../../../PROGRESS.md                  # phase tracker
---

# JobScope — Design

## 0. Context

JobScope is a personal LinkedIn job-market intelligence tool built on Jetro,
submitted as Round 2 of the Berrywise (berrywise.ai) hiring process. The
parallel to Berrywise's domain is intentional: raw data → scoring → visual
intelligence → human decision.

- **It is NOT an auto-applier.** It never clicks Apply.
- **It IS a read-only intelligence layer** that turns a chaotic LinkedIn job
  search into a measurable, queryable workflow.
- **MVP scope:** Lean MVP + per-job resume tailoring. 1-week build.

The full vision and rationale live in `jobscope_final_brief.md`.

## 1. Locked-in decisions (from brainstorming)

| Decision | Value |
|---|---|
| Scope | Lean MVP + per-job resume tailoring |
| JD ingestion | Selenium primary, full commitment (no paste fallback) |
| Scraper ↔ canvas coupling | **None.** Canvas is read-only. Decisions via tkinter popup in the scraper. |
| Canvas split | Two canvases: Live cockpit + Historical dashboard |
| AI provider | Gemini 2.5 Flash Lite (3 API keys, rotated on rate limit) |
| Config source | Lifted *values* from `auto_job_applier_linkedIn/config/*` into `jobscope/config.py`. Reference repo is a donor, then deleted. |
| DB | DuckDB ≥ 1.0 at `projects/jobscope/jobscope.duckdb` |
| Profile | `jet_parse` resume PDF → `profile.json` (source of truth) → mirrored to DuckDB |
| Live↔canvas channel | `current_job.json` file snapshot, atomic write |
| Decision UI | `tkinter` modal popup with Apply / Skip / Bookmark |
| Optional | Light C2 wiring inside the live canvas only (frame↔frame fan-out from one shared refresh-binding) |

## 2. System architecture

Three independent units, talking through DuckDB + a JSON snapshot file. No
sockets, no bidirectional canvas state machine. The canvas never talks to the
scraper.

```
┌──────────────────────────┐
│  jobscope_bot (Python)   │
│  Selenium + Gemini       │
│  - login → search → list │
│  - for each listing:     │
│      extract JD          │
│      Gemini analyze      │
│      write DuckDB        │
│      write JSON snapshot │
│      tkinter popup       │
│      record decision     │
└─────────┬────────────────┘
          │ writes
          ▼
   ┌──────────────────┐
   │ jobscope.duckdb  │   single source of truth (historical)
   │ + current_job.   │   live snapshot (file, atomic rename)
   │   json           │
   └─────────┬────────┘
             │ refresh-bindings poll
             ▼
┌─────────────────────┐    ┌──────────────────────┐
│ Live Canvas (2s)    │    │ Historical (30s)     │
│ reads JSON only     │    │ reads DuckDB         │
└─────────────────────┘    └──────┬───────────────┘
                                  │
                                  ▼  jet_deploy
                            public URL
```

**Invariants**

- Scraper writes DuckDB + `current_job.json`. Nothing else.
- Canvas frames read DuckDB (read-only conns) or `current_job.json`. Nothing else.
- Decisions happen in the Python tkinter popup, never in the canvas.
- `current_job.json` atomic write (`.tmp` + `os.replace`) so refresh-bindings
  never see a half-written file.

**Live-canvas C2 fan-out (the only canvas-side messaging):** one refresh-binding
script (`refresh_current_job.py`) is attached to a single hub frame. It reads
`current_job.json` and uses `__JET.send("current_job", payload)` to broadcast
to subscriber frames (skills / fit_gauge / experience / etc.), each listening
via `__JET.on("current_job", ...)`. Live canvas runs in C2 mode with one wire.
The historical canvas does NOT use C2 — each frame has its own refresh binding
and reads DuckDB directly.

**Module boundaries** — only `orchestrator.py` imports across boundaries.

| Module | One purpose | Talks to |
|---|---|---|
| `jobscope.scraper.*` | Drive Chrome through LinkedIn, extract JD | Selenium |
| `jobscope.ai.*` | Job payload + profile → `JobAnalysis` | Gemini |
| `jobscope.db.*` | Persist + query DuckDB | DuckDB |
| `jobscope.state.snapshot` | Atomic read/write of `current_job.json` | filesystem |
| `jobscope.decision.popup` | tkinter modal → returns user choice | tkinter |
| `jobscope.profile.*` | Build `profile.json` from PDF + configs, sync to DB | jet_parse, DuckDB |
| `jobscope.orchestrator` | Wire all of the above | everything |

## 3. State machine, refresh, staleness, reset

### 3.1 `current_job.json` is the live snapshot

```json
{
  "state": "analyzed",
  "session_id": "2026-05-25T14:32:08-a8f3",
  "job_id": "3812938291",
  "scraper_pid": 18472,
  "last_updated_at": "2026-05-25T14:33:11.482Z",
  "search_term": "AWS Engineer",
  "page": 2,
  "position_on_page": 4,
  "title": "Senior AWS Engineer",
  "company": "Acme",
  "analysis": { ... full Gemini JSON ... },
  "stats": { "evaluated": 12, "applied": 2, "skipped": 9, "bookmarked": 1, "avg_fit": 64.2 }
}
```

`state ∈ {idle, loading, analyzing, analyzed, decided, error, stopped}`.

Live cockpit reads **only this file** (no DuckDB on the live path).
DuckDB is read by the historical canvas and the session-KPI bar.

### 3.2 Refresh cadence

| Frame | Source | Interval |
|---|---|---|
| Live cockpit (all live frames) | `current_job.json` | **2 s** |
| Session KPI bar (lives on live canvas) | DuckDB read-only | **5 s** |
| Historical canvas | DuckDB read-only | **30 s** |
| Deployed historical | `__JET.query()` in frame | on load + 30s |

### 3.3 Staleness handling

- **Scraper hung:** frames check `last_updated_at`. `<10s` normal, `10-60s` "● Scraper idle", `>60s` yellow "Scraper unresponsive" banner, file missing → "Bot not running" placeholder.
- **Gemini error on a job:** `state="error"` in snapshot, with `error.kind` (`rate_limited | parse_error | network | timeout`) → red error chip on analysis panel; rest of frame stays functional. Scraper auto-retries once, then logs `failed_jobs` and moves on.
- **Refresh-script frozen:** each refresh output includes `_meta.computed_at`. If unchanged for 3 intervals → frame shows "⚠ Frame frozen" so we can detect a broken binding fast.

### 3.4 Reset (three flavors)

| Type | Trigger | Action |
|---|---|---|
| Session reset (soft, automatic) | Bot startup | New `session_id`. `current_job.json` → `{state:"idle", session_id: new}`. Historical canvas has a "this session / all" toggle. |
| Live cockpit clear (soft, manual) | `python -m jobscope clear-live` | Overwrite `current_job.json` with idle state. |
| Hard reset (destructive) | `python -m jobscope reset --confirm` | Archive DB → `.bak-{timestamp}`, drop+recreate tables, delete `current_job.json`. Used for clean demo seeding. |

### 3.5 Bot lifecycle

```
[start]
  ↓  current_job.json: state=idle, new session_id, INSERT INTO sessions
[search + filter]   (lifted from runAiBot.apply_filters)
  ↓
[next listing] ←─────────────────────────────┐
  ↓  state=loading                            │
[extract JD] (lifted from runAiBot.get_*)     │
  ↓  state=analyzing                          │
[Gemini analyze]                              │
  ↓  on success state=analyzed; on fail err   │
[tkinter popup: Apply / Skip / Bookmark]      │
  ↓  state=decided, decision row written      │
[next] ───────────────────────────────────────┘

Ctrl+C → graceful: state=stopped + session summary
Crash  → next start archives stale snapshot, opens new session
LinkedIn "Applied" badge auto-detected (source = "auto_detected_applied")
```

## 4. DuckDB schema

Requires `duckdb >= 1.0`. Lives at `projects/jobscope/jobscope.duckdb`.

```sql
CREATE TABLE IF NOT EXISTS jobs (
  job_id            VARCHAR PRIMARY KEY,
  session_id        VARCHAR NOT NULL,
  scraped_at        TIMESTAMPTZ NOT NULL,
  search_term       VARCHAR,
  title             VARCHAR,
  company           VARCHAR,
  location          VARCHAR,
  work_style        VARCHAR,            -- 'Remote'|'Hybrid'|'On-site'
  posted_relative   VARCHAR,
  experience_text   VARCHAR,
  experience_min    INTEGER,
  experience_max    INTEGER,
  salary_min_lpa    DOUBLE,
  salary_max_lpa    DOUBLE,
  salary_text       VARCHAR,
  jd_full_text      TEXT,
  jd_url            VARCHAR,
  analysis_status   VARCHAR NOT NULL DEFAULT 'pending',  -- pending|analyzed|failed
  analysis_error    VARCHAR
);

CREATE TABLE IF NOT EXISTS analyses (
  analysis_id        VARCHAR PRIMARY KEY,         -- uuid4
  job_id             VARCHAR NOT NULL,
  prompt_version     VARCHAR NOT NULL,
  model_name         VARCHAR NOT NULL,
  analyzed_at        TIMESTAMPTZ NOT NULL,
  latency_ms         INTEGER,
  fit_score          INTEGER,
  experience_verdict VARCHAR,    -- in_range|under|over|way_over
  jd_quality         VARCHAR,    -- well_written|average|vague
  red_flags          JSON,       -- [{kind, text}]
  recommendation     TEXT,
  resume_tailoring   TEXT,
  raw_response       JSON        -- full Gemini JSON
);

CREATE TABLE IF NOT EXISTS job_skills (
  job_id            VARCHAR NOT NULL,
  skill_canonical   VARCHAR NOT NULL,
  skill_as_written  VARCHAR NOT NULL,
  kind              VARCHAR NOT NULL,   -- required|nice_to_have
  PRIMARY KEY (job_id, skill_canonical, kind)
);

CREATE TABLE IF NOT EXISTS skills_canonical (
  skill_canonical   VARCHAR PRIMARY KEY,
  display_name      VARCHAR NOT NULL,
  category          VARCHAR,
  aliases           JSON
);

CREATE TABLE IF NOT EXISTS user_skills (
  skill_canonical   VARCHAR PRIMARY KEY,
  proficiency       VARCHAR,
  years             DOUBLE
);

CREATE TABLE IF NOT EXISTS user_profile (
  id                INTEGER PRIMARY KEY,    -- always 1
  full_name         VARCHAR,
  current_role      VARCHAR,
  current_company   VARCHAR,
  experience_years  DOUBLE,
  current_ctc_lpa   DOUBLE,
  expected_ctc_lpa  DOUBLE,
  current_location  VARCHAR,
  willing_locations JSON,
  certifications    JSON,
  updated_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS decisions (
  decision_id       VARCHAR PRIMARY KEY,
  job_id            VARCHAR NOT NULL,
  session_id        VARCHAR NOT NULL,
  decided_at        TIMESTAMPTZ NOT NULL,
  decision          VARCHAR NOT NULL,         -- apply|skip|bookmark
  source            VARCHAR NOT NULL,         -- user|auto_detected_applied
  notes             TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id        VARCHAR PRIMARY KEY,
  started_at        TIMESTAMPTZ NOT NULL,
  ended_at          TIMESTAMPTZ,
  search_terms      JSON,
  search_location   VARCHAR,
  filters_applied   JSON,
  ended_reason      VARCHAR
);

CREATE TABLE IF NOT EXISTS session_state (
  id                INTEGER PRIMARY KEY,      -- always 1
  current_session_id VARCHAR,
  current_job_id    VARCHAR,
  last_active_at    TIMESTAMPTZ
);
INSERT OR IGNORE INTO session_state(id) VALUES (1);
```

**Views**

```sql
CREATE OR REPLACE VIEW v_job_analysis AS
SELECT j.*,
       a.analysis_id, a.fit_score, a.experience_verdict, a.jd_quality,
       a.red_flags, a.recommendation, a.resume_tailoring, a.analyzed_at, a.model_name,
       (SELECT LIST(decision ORDER BY decided_at DESC)
          FROM decisions d WHERE d.job_id = j.job_id) AS decision_history,
       (SELECT decision FROM decisions d
          WHERE d.job_id = j.job_id ORDER BY d.decided_at DESC LIMIT 1) AS latest_decision
FROM jobs j
LEFT JOIN (
  SELECT * FROM analyses
  QUALIFY ROW_NUMBER() OVER (PARTITION BY job_id ORDER BY analyzed_at DESC) = 1
) a USING (job_id);

CREATE OR REPLACE VIEW v_skill_gaps AS
SELECT js.skill_canonical, sc.display_name,
       COUNT(DISTINCT js.job_id) AS jobs_asking,
       COUNT(DISTINCT js.job_id) FILTER (
         WHERE js.skill_canonical NOT IN (SELECT skill_canonical FROM user_skills)
       ) AS jobs_where_missing,
       AVG(a.fit_score) AS avg_fit_when_asked
FROM job_skills js
LEFT JOIN skills_canonical sc USING (skill_canonical)
LEFT JOIN v_job_analysis a USING (job_id)
WHERE js.kind = 'required'
GROUP BY js.skill_canonical, sc.display_name
ORDER BY jobs_where_missing DESC;

CREATE OR REPLACE VIEW v_search_term_report AS
SELECT j.search_term,
       COUNT(*) AS jobs_seen,
       ROUND(AVG(a.fit_score), 1) AS avg_fit,
       COUNT(*) FILTER (WHERE d.decision = 'apply')  AS applied,
       COUNT(*) FILTER (WHERE d.decision = 'skip')   AS skipped,
       ROUND(100.0 * COUNT(*) FILTER (WHERE d.decision = 'apply')
             / NULLIF(COUNT(*), 0), 1) AS apply_rate_pct
FROM jobs j
LEFT JOIN v_job_analysis a USING (job_id)
LEFT JOIN LATERAL (
  SELECT decision FROM decisions
  WHERE job_id = j.job_id ORDER BY decided_at DESC LIMIT 1
) d ON true
GROUP BY j.search_term
ORDER BY avg_fit DESC;

CREATE OR REPLACE VIEW v_current_session_stats AS
SELECT s.session_id, s.started_at,
       COUNT(DISTINCT j.job_id) AS jobs_evaluated,
       COUNT(DISTINCT d.job_id) FILTER (WHERE d.decision='apply')    AS applied,
       COUNT(DISTINCT d.job_id) FILTER (WHERE d.decision='skip')     AS skipped,
       COUNT(DISTINCT d.job_id) FILTER (WHERE d.decision='bookmark') AS bookmarked,
       ROUND(AVG(a.fit_score), 1) AS avg_fit
FROM sessions s
LEFT JOIN jobs j USING (session_id)
LEFT JOIN decisions d USING (session_id)
LEFT JOIN v_job_analysis a ON a.job_id = j.job_id
WHERE s.session_id = (SELECT current_session_id FROM session_state WHERE id=1)
GROUP BY s.session_id, s.started_at;
```

**Connection rules**

| Process | Mode |
|---|---|
| `jobscope_bot` (scraper) | read-write, single long-lived connection |
| Live cockpit refresh (2s) | **not used** — reads JSON file only |
| Session KPI refresh (5s) | `read_only=True`, open + query + close per refresh |
| Historical refresh (30s) | `read_only=True`, same pattern |
| Deployed dashboard | `__JET.query()`, read-only in frame |

DuckDB ≥ 1.0 allows concurrent read connections while a writer holds the file.
FOREIGN KEYs are documentation only — DuckDB doesn't enforce them. No manual
indexes (columnar zone maps handle it).

## 5. The Gemini prompt

### 5.1 Principles

- Strict JSON output. `response_mime_type="application/json"` + `response_schema=JobAnalysis`. Pydantic validates after. One retry on validation/timeout, then `analysis_status='failed'`.
- Full profile injected (skills + proficiency + years + projects + certs + salary).
- Canonical skills list passed as hint — model must reuse slugs from this list when applicable, invent slug-case names otherwise.
- Reasoning before scoring (`fit_rationale` field) to avoid default-75 anchoring.
- `temperature=0.2`. `gemini-2.5-flash-lite` model.

### 5.2 Pydantic schema

```python
class RedFlag(BaseModel):
    kind: Literal["staffing_recruiting", "experience_mismatch",
                  "skill_domain_mismatch", "visa_or_citizenship",
                  "salary_below_expected", "vague_jd"]
    text: str

class JDSkill(BaseModel):
    canonical: str
    as_written: str
    kind: Literal["required", "nice_to_have"]

class JobAnalysis(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    fit_rationale: str
    experience_verdict: Literal["in_range", "under", "over", "way_over"]
    experience_min_years: int | None
    experience_max_years: int | None
    skills: list[JDSkill]
    red_flags: list[RedFlag]
    jd_quality: Literal["well_written", "average", "vague"]
    recommendation: str
    resume_tailoring: str
    salary_min_lpa: float | None
    salary_max_lpa: float | None
```

### 5.3 System prompt (template, see `jobscope/ai/prompts.py` for live version)

Tells Gemini: be honest not encouraging; use 6-flag taxonomy; weighted scoring
(skills 50% / experience 25% / red flags 25%); resume_tailoring must reference
candidate's actual projects by name.

### 5.4 Retry / cost / quota

- **Cost:** ~3,100 tokens/call on Flash Lite ≈ $0.0003. 100 jobs ≈ 3¢.
- **Latency:** 2-4 s typical, 8 s p95.
- **Timeout:** 30 s, one retry.
- **Rate limit:** rotate to next key in `GEMINI_API_KEYS` (3 keys), retry immediately.
- **Validation fail:** one retry, then mark failed.
- `PROMPT_VERSION = "1.0.0"` — stored on every `analyses` row.

## 6. File & module layout

```
JobScope/
├── auto_job_applier_linkedIn/       # reference donor; delete post-MVP
├── jobscope/                        # our self-contained Python package
│   ├── __main__.py
│   ├── config.py                    # all defaults + .env loading
│   ├── cli.py                       # run / reset / clear-live / seed-skills / parse-resume / login-only
│   ├── db/         schema.sql, views.sql, seed_skills.csv, connection.py, repo.py
│   ├── scraper/    browser.py, login.py, search.py, listing.py, extract.py,
│   │               applied_detector.py, _clickers.py
│   ├── ai/         client.py, prompts.py, schema.py, analyzer.py
│   ├── state/      snapshot.py
│   ├── decision/   popup.py
│   ├── profile/    parse_resume.py, normalize.py
│   ├── orchestrator.py              # only cross-boundary importer
│   └── utils/      logging.py, ids.py
├── projects/jobscope/
│   ├── project.json
│   ├── jobscope.duckdb              # gitignored
│   ├── profile.json                 # committed
│   ├── resume.pdf                   # committed; copied from reference
│   └── state/current_job.json       # gitignored
├── .jetro/
│   ├── frames/                      # 13 HTML frames (9 live + 4 historical)
│   │   # live: bot_status, header, fit_gauge, skills, experience, red_flags,
│   │   #       recommendation, resume_tailoring, session_kpis
│   │   # historical: skill_gaps, fit_distribution, salary_map, search_term_report
│   ├── scripts/                     # 6 refresh-binding scripts
│   │   # refresh_current_job (live hub), refresh_session_kpis,
│   │   # refresh_skill_gaps, refresh_fit_distribution,
│   │   # refresh_salary_map, refresh_search_term_report
│   └── skills/jobscope_dashboard.md # the shipped Jetro skill (path verified at impl time)
├── logs/jobscope.log                # gitignored
├── docs/superpowers/specs/2026-05-25-jobscope-design.md
├── tests/
├── .env                             # gitignored
├── .env.example                     # committed
├── pyproject.toml
└── README.md
```

### What gets lifted from the reference

| Reference | Lifted into | Notes |
|---|---|---|
| `modules/open_chrome.py` | `jobscope/scraper/browser.py` | Slimmed: drop resume-gen + extension toggles |
| `runAiBot.py::login_LN` | `jobscope/scraper/login.py` | Keep 2FA pause + retry |
| `runAiBot.py::apply_filters`, `set_search_location` | `jobscope/scraper/search.py` | Reuse filter UI selectors |
| `runAiBot.py::get_job_main_details`, `get_job_description` | `jobscope/scraper/extract.py` | Reuse JD/title/company selectors |
| `runAiBot.py::extract_years_of_experience` | `jobscope/scraper/extract.py` | Reuse regex |
| `modules/clickers_and_finders.py` | `jobscope/scraper/_clickers.py` | The most-undervalued file in the reference |
| `modules/ai/geminiConnections.py` | `jobscope/ai/client.py` | Replace raw HTTP with official `google-genai` SDK to get native `response_schema` |
| `config/secrets.py` values | `.env` | Gemini keys, LinkedIn creds — NOT committed |
| `config/search.py` / `personals.py` / `settings.py` values | `jobscope/config.py` | As Python constants |
| `Rajarshi_Bose_Resume_2026-05-13.pdf` | `projects/jobscope/resume.pdf` | Copy the file |

### `jobscope/config.py` shape

```python
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()

REPO_ROOT     = Path(__file__).resolve().parent.parent
PROJECT_ROOT  = REPO_ROOT / "projects" / "jobscope"
DB_PATH       = PROJECT_ROOT / "jobscope.duckdb"
PROFILE_PATH  = PROJECT_ROOT / "profile.json"
RESUME_PDF    = PROJECT_ROOT / "resume.pdf"
SNAPSHOT_PATH = PROJECT_ROOT / "state" / "current_job.json"
LOG_PATH      = REPO_ROOT / "logs" / "jobscope.log"

LINKEDIN_USERNAME = os.environ["LINKEDIN_USERNAME"]
LINKEDIN_PASSWORD = os.environ["LINKEDIN_PASSWORD"]
GEMINI_API_KEYS   = [k.strip() for k in os.environ["GEMINI_API_KEYS"].split(",") if k.strip()]

SEARCH_TERMS      = ["AI Engineer", "ASP.NET Developer", "Software Developer",
                     "Full Stack Developer", "AWS Engineer"]
SEARCH_LOCATION   = "Bengaluru, Karnataka, India"
DATE_POSTED       = "Past 24 hours"
EASY_APPLY_ONLY   = True
EXPERIENCE_LEVELS = ["Entry level", "Associate", "Mid-Senior level"]
JOB_TYPES         = ["Full-time"]
ON_SITE           = ["Remote", "Hybrid", "On-site"]
SWITCH_AFTER      = 5

CLICK_GAP_SEC      = 2
STEALTH_MODE       = True
RUN_IN_BACKGROUND  = False
DISABLE_EXTENSIONS = True

FULL_NAME             = "Rajarshi Bose"
PHONE                 = "9731173375"
CURRENT_CITY          = "Bangalore"
CURRENT_CTC_LPA       = 7.5
EXPECTED_CTC_LPA      = 12.0
EXPERIENCE_YEARS      = 2.0

GEMINI_MODEL       = "gemini-2.5-flash-lite"
PROMPT_VERSION     = "1.0.0"
GEMINI_TIMEOUT_SEC = 30
GEMINI_TEMPERATURE = 0.2

LIVE_REFRESH_MS         = 2000
HISTORICAL_REFRESH_MS   = 30000
SESSION_KPI_REFRESH_MS  = 5000
SNAPSHOT_STALE_WARN_SEC = 10
SNAPSHOT_STALE_FAIL_SEC = 60
```

### CLI entry points

```
python -m jobscope parse-resume     # one-time: PDF → profile.json + user_skills upsert
python -m jobscope seed-skills      # one-time: load skills_canonical from CSV
python -m jobscope run              # start the bot
python -m jobscope clear-live       # reset current_job.json to idle
python -m jobscope reset --confirm  # wipe DB (archives first)
python -m jobscope login-only       # debug: just open Chrome + log in
```

## 7. Testing, error handling, observability

### 7.1 Test layer

| Layer | Type | Tool |
|---|---|---|
| `ai.schema` Pydantic | unit | pytest |
| `ai.analyzer` retry/rotation | unit (mocked Gemini) | pytest + mock |
| `scraper.extract` against saved listings | unit | pytest + fixtures `tests/fixtures/listings/*.html` |
| `extract_years_of_experience` | unit (parametrized) | pytest |
| `db.repo` + views | integration on `:memory:` | pytest |
| `state.snapshot` atomic write | unit | pytest + tmp_path |
| `profile.parse_resume` smoke | manual + 1 pytest | jet_parse |
| Refresh scripts emit valid JSON | smoke against seeded DB | pytest |
| Orchestrator end-to-end | manual + demo recording | — |
| Selenium login/search/iterate | manual | — |
| Canvas frames | manual visual | — |

**Fixtures up front**

- 3-5 saved LinkedIn job listing HTML files
- `tests/fixtures/seed.duckdb` — ~20 fake jobs + analyses
- `tests/fixtures/profile.json`

### 7.2 Failure matrix

| Failure | Detection | Recovery | User sees |
|---|---|---|---|
| Login fails | `login_LN` raises | Exit, hint "Check .env" | terminal error |
| Captcha / verify wall | post-login DOM check | Pause; tkinter "Solve then OK" | popup |
| Filter apply fails | element-not-found | Log + screenshot, skip filter | log only |
| JD extraction empty | empty-string check | `analysis_status='failed'`, skip Gemini | red chip on cockpit |
| Gemini timeout (30s) | client timeout | One retry same key | brief "retrying" |
| Gemini 429 | rate-limit error | Rotate key, retry immediately | invisible |
| Invalid Gemini JSON | Pydantic | One retry, then fail | red chip |
| All keys exhausted | every key 429 in last 60s | Pause 60s, retry once, else fail session | terminal + snapshot error |
| DuckDB locked | IOError | 100ms backoff x5 then abort job | log + red chip |
| Snapshot mid-write | atomic rename prevents | n/a | n/a |
| Refresh script crash | Jetro Output panel | We fix and re-bind | "Frame frozen" indicator |
| Bot crashed mid-job | next startup detects stale snapshot | Archive to `state/crashed/{ts}.json`, fresh start | invisible |
| LinkedIn DOM drift | extraction returns junk | Pydantic catches; we update selectors | red chip |
| Ctrl+C | SIGINT handler | Wait ≤5s graceful, write `state=stopped`, close DB + browser | clean exit |
| Disk full | OSError on commit | Crash log + exit | terminal error |

**Contract:** bot never crashes the canvas; canvas never blocks the bot.

### 7.3 Logging

Structured JSONL → `logs/jobscope.log`, rotated at 10MB.

```json
{"ts":"...","level":"INFO","module":"orchestrator","job_id":"...","msg":"job_extracted","title":"..."}
{"ts":"...","level":"INFO","module":"ai.analyzer","job_id":"...","msg":"analysis_complete","fit_score":67,"latency_ms":2840,"prompt_version":"1.0.0"}
{"ts":"...","level":"WARNING","module":"ai.analyzer","msg":"gemini_rate_limit","key_index":0,"action":"rotating"}
{"ts":"...","level":"ERROR","module":"scraper.extract","job_id":"...","msg":"jd_empty"}
```

Post-mortem via `SELECT * FROM read_json('logs/jobscope.log') WHERE level='ERROR'`.

### 7.4 On-canvas observability

A "Bot status" frame at the top of the live canvas:
- `● Live` / `● Slow` / `● Stalled` indicator from `last_updated_at`
- Last 3 warnings/errors as scrolling list
- Session uptime + jobs/min throughput

### 7.5 Pre-demo verification

- [ ] `python -m jobscope reset --confirm`, then seed 50-100 real evaluated jobs
- [ ] `jet_deploy` the historical canvas; verify URL in incognito
- [ ] Run bot 10 jobs end-to-end on recording — confirm live updates
- [ ] Publish historical dashboard as LDF (`jet_doc`) as downloadable artifact
- [ ] Verify Jetro skill discoverable: `jet_skill({ name: "JobScope Dashboard" })`
- [ ] Grep `logs/jobscope.log` for errors during the recording
- [ ] Smoke on a clean Windows machine (repo + Python + Chrome only)

## 8. Out of scope (deferred)

Not in MVP. Schema accommodates without migrations.

- Talking points generator (per applied job)
- Interview prep seeds
- Response tracking (`responses` table)
- Skill adjacency map
- Learning priority recommendations
- Company watchlist + "frequently reposting" flag
- Application funnel (will-apply → applied)
- Weekly trend lines
- Bookmark resurfacing UI

## 9. Open risks

| Risk | Mitigation |
|---|---|
| LinkedIn anti-bot blocks demo day | `stealth_mode=True`; manual captcha-solve via popup; secondary "logged in already" Chrome profile if needed |
| Gemini schema enforcement fragility on Flash Lite | Pydantic + retry; if pathological, can demote to Flash 2.0 with same prompt |
| DuckDB read/write contention under refresh load | Refreshes use read-only conns; scraper commits per-job; we'd see this in stress test |
| Selenium selector drift mid-week | Save 3-5 HTML fixtures from day 1; if selectors break, fix against fixtures first |
| Demo machine variation | Pin Python 3.11, Chrome stable, `duckdb>=1.0` in pyproject; pre-demo smoke on clean install |

## 10. Definition of done (MVP)

- [ ] `python -m jobscope run` logs in, iterates 5+ jobs end-to-end with no manual fix
- [ ] Live cockpit shows 9 working frames updating each job (≤3s lag) — incl. bot status
- [ ] Historical canvas shows 4 working charts from real seeded data
- [ ] tkinter popup records all 3 decision types into `decisions` table
- [ ] LinkedIn "Applied" badge auto-detected and recorded (`source='auto_detected_applied'`)
- [ ] `jet_deploy` produces a live public URL of the historical dashboard
- [ ] `.jetro/skills/jobscope_dashboard.md` discoverable via `jet_skill`
- [ ] README.md has setup steps that work on a fresh Windows machine
- [ ] Demo recording: 5 minutes, narrates the workflow + shows the deployed URL
