# JobScope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP described in `docs/superpowers/specs/2026-05-25-jobscope-design.md` — a Selenium-driven LinkedIn job-evaluator that calls Gemini per JD, writes to DuckDB, renders live + historical analysis on two Jetro canvases, and lets the user decide via a tkinter popup.

**Architecture:** One Python package `jobscope/` with three independent units (scraper / AI / DB) wired by `orchestrator.py`. Canvas is read-only. Live cockpit reads `current_job.json` snapshot (atomic file write); historical canvas reads DuckDB via read-only connections. Decisions happen in a tkinter modal popup inside the scraper process.

**Tech Stack:** Python 3.11, `duckdb>=1.0`, `selenium`, `undetected-chromedriver`, `google-genai`, `pydantic`, `python-dotenv`, `click`, `pytest`, `beautifulsoup4`. tkinter is stdlib.

**Prerequisites for the executor:**
- Python 3.11 installed and on `PATH`
- Google Chrome (any recent stable)
- Read access to `auto_job_applier_linkedIn/` (the reference repo we'll lift code from)
- Read access to the design spec and PROJECT.md / PROGRESS.md

---

## File Structure (locked from spec §6)

```
jobscope/
├── __init__.py
├── __main__.py                  # CLI dispatcher
├── config.py                    # all constants + .env loading
├── cli.py                       # click commands
├── db/
│   ├── __init__.py
│   ├── schema.sql               # CREATE TABLE statements
│   ├── views.sql                # v_job_analysis etc.
│   ├── seed_skills.csv          # canonical skill seed (~80 rows)
│   ├── connection.py            # rw + ro helpers
│   └── repo.py                  # upsert/insert/query helpers
├── scraper/
│   ├── __init__.py
│   ├── _clickers.py             # safe_click / wait helpers (lifted)
│   ├── browser.py               # undetected-chromedriver setup
│   ├── login.py                 # LinkedIn login flow
│   ├── search.py                # apply filters, set location
│   ├── listing.py               # iterate result list, pagination
│   ├── extract.py               # extract JD, parse years
│   └── applied_detector.py      # poll Apply-button DOM state
├── ai/
│   ├── __init__.py
│   ├── schema.py                # Pydantic models
│   ├── client.py                # Gemini client + key rotator
│   ├── prompts.py               # SYSTEM_PROMPT + builder
│   └── analyzer.py              # analyze() with retry
├── state/
│   ├── __init__.py
│   └── snapshot.py              # atomic JSON read/write
├── decision/
│   ├── __init__.py
│   └── popup.py                 # tkinter modal
├── profile/
│   ├── __init__.py
│   ├── parse_resume.py          # jet_parse wrapper
│   └── normalize.py             # write profile.json + sync DB
├── orchestrator.py              # main loop
└── utils/
    ├── __init__.py
    ├── logging.py               # JSONL logger
    └── ids.py                   # uuid + session_id factories

projects/jobscope/
├── project.json
├── profile.json                 # committed
├── resume.pdf                   # copied from reference
└── state/
    └── current_job.json         # gitignored

.jetro/
├── frames/                      # 13 HTML files (see Phase 7)
├── scripts/                     # 6 refresh-binding scripts
└── skills/jobscope_dashboard.md # the shipped Jetro skill

tests/
├── conftest.py
├── fixtures/
│   ├── listings/                # saved LinkedIn JD HTML
│   ├── seed.duckdb              # ~20 fake rows
│   └── profile.json
├── ai/                          # tests for jobscope/ai/
├── db/
├── scraper/
└── state/

logs/jobscope.log                # JSONL, gitignored
```

---

## Phase 0 — Repo init & gitignore

### Task 0.1: Initialize git and write .gitignore

**Files:**
- Create: `.gitignore`
- Init: git repo at repo root

- [ ] **Step 1: Init the repo**

```bash
git init
git branch -M main
```

- [ ] **Step 2: Write .gitignore**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/

# Env / secrets
.env

# JobScope runtime
projects/jobscope/jobscope.duckdb
projects/jobscope/jobscope.duckdb.bak-*
projects/jobscope/state/current_job.json
projects/jobscope/state/crashed/
logs/

# IDE
.vscode/
.idea/

# Jetro
.jetro/cache/
.jetro/output/
```

- [ ] **Step 3: First commit**

```bash
git add .gitignore PROJECT.md PROGRESS.md docs/
git commit -m "chore: init repo with onboarding docs and approved spec"
```

---

## Phase 1 — Package skeleton, deps, config

### Task 1.1: pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "jobscope"
version = "0.1.0"
description = "Personal LinkedIn job market intelligence tool, built on Jetro"
requires-python = ">=3.11"
dependencies = [
  "duckdb>=1.0",
  "selenium>=4.20",
  "undetected-chromedriver>=3.5",
  "google-genai>=0.3",
  "pydantic>=2.7",
  "python-dotenv>=1.0",
  "click>=8.1",
  "beautifulsoup4>=4.12",
  "certifi>=2024.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-mock>=3.12",
]

[project.scripts]
jobscope = "jobscope.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["jobscope*"]

[tool.setuptools.package-data]
jobscope = ["db/*.sql", "db/*.csv"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create venv and install**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Expected: `Successfully installed jobscope-0.1.0 duckdb-... ...`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with project deps"
```

### Task 1.2: Package skeleton — empty __init__ files

**Files:**
- Create: `jobscope/__init__.py`, `jobscope/db/__init__.py`, `jobscope/scraper/__init__.py`, `jobscope/ai/__init__.py`, `jobscope/state/__init__.py`, `jobscope/decision/__init__.py`, `jobscope/profile/__init__.py`, `jobscope/utils/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create all __init__.py files**

```bash
# Windows PowerShell — run from repo root
$dirs = @(
  "jobscope","jobscope/db","jobscope/scraper","jobscope/ai",
  "jobscope/state","jobscope/decision","jobscope/profile","jobscope/utils",
  "tests","tests/ai","tests/db","tests/scraper","tests/state",
  "tests/fixtures","tests/fixtures/listings"
)
foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  if (-not $d.StartsWith("tests/fixtures")) {
    New-Item -ItemType File -Force -Path "$d/__init__.py" | Out-Null
  }
}
```

- [ ] **Step 2: Set jobscope/__init__.py version**

Write to `jobscope/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write tests/conftest.py with shared fixtures**

```python
"""Shared pytest fixtures."""
from pathlib import Path
import pytest
import duckdb

FIXTURE_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def fresh_duckdb(tmp_path):
    """In-memory DuckDB initialized with our schema."""
    from jobscope.db.connection import init_schema
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    init_schema(conn)
    yield conn
    conn.close()
```

- [ ] **Step 4: Verify pytest discovers tests**

Run: `pytest --collect-only`
Expected: "no tests ran" — passes without error (no tests yet).

- [ ] **Step 5: Commit**

```bash
git add jobscope/ tests/
git commit -m "chore: scaffold jobscope package and test layout"
```

### Task 1.3: .env scaffolding

**Files:**
- Create: `.env.example`
- Create: `.env` (NOT committed)

- [ ] **Step 1: Write .env.example**

```
# Copy to .env and fill in.
# LinkedIn login (used by jobscope/scraper/login.py)
LINKEDIN_USERNAME=you@example.com
LINKEDIN_PASSWORD=changeme

# Gemini API keys — comma-separated. Client rotates on rate limit.
# Get free keys at https://aistudio.google.com/app/apikey
GEMINI_API_KEYS=AIza...,AIza...,AIza...
```

- [ ] **Step 2: Write .env (NOT committed — gitignored)**

Lift values from `auto_job_applier_linkedIn/config/secrets.py`:
- `LINKEDIN_USERNAME` ← `secrets.py::username`
- `LINKEDIN_PASSWORD` ← `secrets.py::password`
- `GEMINI_API_KEYS` ← `secrets.py::review_gemini_api_keys` joined with commas (3 keys)

- [ ] **Step 3: Verify .env is gitignored**

Run: `git status --short .env`
Expected: empty output (file is ignored).

- [ ] **Step 4: Commit only the example**

```bash
git add .env.example
git commit -m "chore: add .env.example template"
```

### Task 1.4: jobscope/config.py

**Files:**
- Create: `jobscope/config.py`

- [ ] **Step 1: Write the config module**

```python
"""Central config. Constants live here; secrets in .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------- paths ----------
REPO_ROOT     = Path(__file__).resolve().parent.parent
PROJECT_ROOT  = REPO_ROOT / "projects" / "jobscope"
DB_PATH       = PROJECT_ROOT / "jobscope.duckdb"
PROFILE_PATH  = PROJECT_ROOT / "profile.json"
RESUME_PDF    = PROJECT_ROOT / "resume.pdf"
SNAPSHOT_PATH = PROJECT_ROOT / "state" / "current_job.json"
CRASHED_DIR   = PROJECT_ROOT / "state" / "crashed"
LOG_PATH      = REPO_ROOT / "logs" / "jobscope.log"

# ---------- secrets ----------
LINKEDIN_USERNAME = os.environ.get("LINKEDIN_USERNAME", "")
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "")
GEMINI_API_KEYS   = [
    k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()
]

# ---------- LinkedIn search ----------
SEARCH_TERMS = [
    "AI Engineer", "ASP.NET Developer", "Software Developer",
    "Full Stack Developer", "AWS Engineer",
]
SEARCH_LOCATION   = "Bengaluru, Karnataka, India"
DATE_POSTED       = "Past 24 hours"
EASY_APPLY_ONLY   = True
EXPERIENCE_LEVELS = ["Entry level", "Associate", "Mid-Senior level"]
JOB_TYPES         = ["Full-time"]
ON_SITE           = ["Remote", "Hybrid", "On-site"]
SWITCH_AFTER      = 5

# ---------- browser ----------
CLICK_GAP_SEC      = 2
STEALTH_MODE       = True
RUN_IN_BACKGROUND  = False
DISABLE_EXTENSIONS = True

# ---------- candidate ----------
FULL_NAME        = "Rajarshi Bose"
PHONE            = "9731173375"
CURRENT_CITY     = "Bangalore"
CURRENT_CTC_LPA  = 7.5
EXPECTED_CTC_LPA = 12.0
EXPERIENCE_YEARS = 2.0

# ---------- AI ----------
GEMINI_MODEL       = "gemini-2.5-flash-lite"
PROMPT_VERSION     = "1.0.0"
GEMINI_TIMEOUT_SEC = 30
GEMINI_TEMPERATURE = 0.2

# ---------- refresh / staleness (ms unless _SEC) ----------
LIVE_REFRESH_MS         = 2000
HISTORICAL_REFRESH_MS   = 30000
SESSION_KPI_REFRESH_MS  = 5000
SNAPSHOT_STALE_WARN_SEC = 10
SNAPSHOT_STALE_FAIL_SEC = 60

def ensure_dirs() -> None:
    """Create runtime directories that must exist."""
    for d in (PROJECT_ROOT / "state", CRASHED_DIR, LOG_PATH.parent):
        d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Smoke test the import**

```bash
python -c "from jobscope import config; config.ensure_dirs(); print(config.DB_PATH)"
```

Expected: prints the absolute DB path; no errors.

- [ ] **Step 3: Commit**

```bash
git add jobscope/config.py
git commit -m "feat(config): central constants module with .env loading"
```

### Task 1.5: utils/logging.py — JSONL logger

**Files:**
- Create: `jobscope/utils/logging.py`
- Test: `tests/test_logging.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_logging.py
import json
import logging
from jobscope.utils.logging import get_logger, configure_logging

def test_logger_emits_jsonl(tmp_path):
    log_file = tmp_path / "test.log"
    configure_logging(log_file)
    log = get_logger("test.module")
    log.info("hello", extra={"job_id": "abc", "msg_kind": "test_event"})
    for h in logging.getLogger().handlers:
        h.flush()
    line = log_file.read_text().strip().splitlines()[0]
    parsed = json.loads(line)
    assert parsed["level"] == "INFO"
    assert parsed["module"] == "test.module"
    assert parsed["job_id"] == "abc"
    assert parsed["msg_kind"] == "test_event"
    assert "ts" in parsed
```

- [ ] **Step 2: Run test, confirm failure**

```bash
pytest tests/test_logging.py -v
```
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement the logger**

```python
# jobscope/utils/logging.py
"""Structured JSONL logging."""
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

class JsonlFormatter(logging.Formatter):
    RESERVED = {
        "name","msg","args","levelname","levelno","pathname","filename",
        "module","exc_info","exc_text","stack_info","lineno","funcName",
        "created","msecs","relativeCreated","thread","threadName",
        "processName","process","message","asctime","taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self.RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

def configure_logging(log_path: Path, level: int = logging.INFO) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    file_h = RotatingFileHandler(
        log_path, maxBytes=10_000_000, backupCount=3, encoding="utf-8"
    )
    file_h.setFormatter(JsonlFormatter())
    root.addHandler(file_h)
    stderr_h = logging.StreamHandler()
    stderr_h.setFormatter(JsonlFormatter())
    root.addHandler(stderr_h)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

- [ ] **Step 4: Run test, confirm pass**

```bash
pytest tests/test_logging.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add jobscope/utils/logging.py tests/test_logging.py
git commit -m "feat(logging): JSONL rotating file logger"
```

### Task 1.6: utils/ids.py — uuid + session_id factories

**Files:**
- Create: `jobscope/utils/ids.py`
- Test: `tests/test_ids.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ids.py
import re
from jobscope.utils.ids import new_session_id, new_uuid

def test_session_id_format():
    sid = new_session_id()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}-[0-9a-f]{4}$", sid), sid

def test_new_uuid_is_unique():
    a, b = new_uuid(), new_uuid()
    assert a != b
    assert len(a) == 36
```

- [ ] **Step 2: Run test, confirm failure**

```bash
pytest tests/test_ids.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# jobscope/utils/ids.py
"""ID generators."""
import secrets
import uuid
from datetime import datetime, timezone

def new_uuid() -> str:
    return str(uuid.uuid4())

def new_session_id() -> str:
    """ISO timestamp + 4-hex suffix. Sortable, readable, unique."""
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return f"{ts}-{secrets.token_hex(2)}"
```

- [ ] **Step 4: Run test, confirm pass**

```bash
pytest tests/test_ids.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/utils/ids.py tests/test_ids.py
git commit -m "feat(utils): id factories for session and row uuids"
```

---

---

## Phase 2 — DuckDB: schema, views, connection, repo, seed

### Task 2.1: db/schema.sql

**Files:**
- Create: `jobscope/db/schema.sql`

- [ ] **Step 1: Write schema.sql**

```sql
-- jobscope schema v1. Requires duckdb >= 1.0.

CREATE TABLE IF NOT EXISTS jobs (
  job_id            VARCHAR PRIMARY KEY,
  session_id        VARCHAR NOT NULL,
  scraped_at        TIMESTAMPTZ NOT NULL,
  search_term       VARCHAR,
  title             VARCHAR,
  company           VARCHAR,
  location          VARCHAR,
  work_style        VARCHAR,
  posted_relative   VARCHAR,
  experience_text   VARCHAR,
  experience_min    INTEGER,
  experience_max    INTEGER,
  salary_min_lpa    DOUBLE,
  salary_max_lpa    DOUBLE,
  salary_text       VARCHAR,
  jd_full_text      TEXT,
  jd_url            VARCHAR,
  analysis_status   VARCHAR NOT NULL DEFAULT 'pending',
  analysis_error    VARCHAR
);

CREATE TABLE IF NOT EXISTS analyses (
  analysis_id        VARCHAR PRIMARY KEY,
  job_id             VARCHAR NOT NULL,
  prompt_version     VARCHAR NOT NULL,
  model_name         VARCHAR NOT NULL,
  analyzed_at        TIMESTAMPTZ NOT NULL,
  latency_ms         INTEGER,
  fit_score          INTEGER,
  experience_verdict VARCHAR,
  jd_quality         VARCHAR,
  red_flags          JSON,
  recommendation     TEXT,
  resume_tailoring   TEXT,
  raw_response       JSON
);

CREATE TABLE IF NOT EXISTS job_skills (
  job_id            VARCHAR NOT NULL,
  skill_canonical   VARCHAR NOT NULL,
  skill_as_written  VARCHAR NOT NULL,
  kind              VARCHAR NOT NULL,
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
  id                INTEGER PRIMARY KEY,
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
  decision          VARCHAR NOT NULL,
  source            VARCHAR NOT NULL,
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
  id                INTEGER PRIMARY KEY,
  current_session_id VARCHAR,
  current_job_id    VARCHAR,
  last_active_at    TIMESTAMPTZ
);

INSERT OR IGNORE INTO session_state(id) VALUES (1);
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/db/schema.sql
git commit -m "feat(db): schema.sql with 9 tables for jobs, analyses, skills, decisions"
```

### Task 2.2: db/views.sql

**Files:**
- Create: `jobscope/db/views.sql`

- [ ] **Step 1: Write views.sql**

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
SELECT js.skill_canonical,
       COALESCE(sc.display_name, js.skill_canonical) AS display_name,
       COUNT(DISTINCT js.job_id) AS jobs_asking,
       COUNT(DISTINCT js.job_id) FILTER (
         WHERE js.skill_canonical NOT IN (SELECT skill_canonical FROM user_skills)
       ) AS jobs_where_missing,
       AVG(a.fit_score) AS avg_fit_when_asked
FROM job_skills js
LEFT JOIN skills_canonical sc USING (skill_canonical)
LEFT JOIN v_job_analysis a USING (job_id)
WHERE js.kind = 'required'
GROUP BY js.skill_canonical, COALESCE(sc.display_name, js.skill_canonical)
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
ORDER BY avg_fit DESC NULLS LAST;

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

- [ ] **Step 2: Commit**

```bash
git add jobscope/db/views.sql
git commit -m "feat(db): canonical views for analysis, skill gaps, search report, session stats"
```

### Task 2.3: db/connection.py

**Files:**
- Create: `jobscope/db/connection.py`
- Test: `tests/db/test_connection.py`

- [ ] **Step 1: Write failing test**

```python
# tests/db/test_connection.py
from jobscope.db.connection import open_rw, open_ro, init_schema

def test_init_schema_creates_tables(tmp_path):
    db_path = tmp_path / "x.duckdb"
    conn = open_rw(db_path)
    init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()}
    assert {"jobs","analyses","job_skills","skills_canonical","user_skills",
            "user_profile","decisions","sessions","session_state"} <= tables
    conn.close()

def test_init_schema_creates_views(tmp_path):
    db_path = tmp_path / "y.duckdb"
    conn = open_rw(db_path)
    init_schema(conn)
    views = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='main' AND table_type='VIEW'"
    ).fetchall()}
    assert {"v_job_analysis","v_skill_gaps","v_search_term_report",
            "v_current_session_stats"} <= views
    conn.close()

def test_ro_connection_cannot_write(tmp_path):
    db_path = tmp_path / "z.duckdb"
    rw = open_rw(db_path)
    init_schema(rw)
    rw.close()
    ro = open_ro(db_path)
    import pytest
    with pytest.raises(Exception):
        ro.execute("INSERT INTO sessions(session_id, started_at) VALUES ('s', now())")
    ro.close()
```

- [ ] **Step 2: Run test, confirm failure**

```bash
pytest tests/db/test_connection.py -v
```

- [ ] **Step 3: Implement connection.py**

```python
# jobscope/db/connection.py
"""DuckDB connection helpers."""
from pathlib import Path
import duckdb

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
VIEWS_PATH = Path(__file__).parent / "views.sql"

def open_rw(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))

def open_ro(db_path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True)

def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply schema.sql and views.sql. Idempotent (CREATE IF NOT EXISTS / OR REPLACE)."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(VIEWS_PATH.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test, confirm pass**

```bash
pytest tests/db/test_connection.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/db/connection.py tests/db/test_connection.py
git commit -m "feat(db): rw/ro connection helpers and schema bootstrap"
```

### Task 2.4: db/seed_skills.csv

**Files:**
- Create: `jobscope/db/seed_skills.csv`

- [ ] **Step 1: Write the seed CSV (80 common tech skills)**

Use this header and seed; aliases are JSON arrays (single quotes outside, double inside):

```csv
skill_canonical,display_name,category,aliases
python,Python,language,"[""python"",""python3""]"
javascript,JavaScript,language,"[""javascript"",""js"",""ecmascript""]"
typescript,TypeScript,language,"[""typescript"",""ts""]"
csharp,C#,language,"[""c#"",""csharp"",""c sharp"",""dotnet language""]"
java,Java,language,"[""java""]"
go,Go,language,"[""go"",""golang""]"
rust,Rust,language,"[""rust"",""rust-lang""]"
cpp,C++,language,"[""c++"",""cpp"",""cplusplus""]"
sql,SQL,language,"[""sql""]"
bash,Bash,language,"[""bash"",""shell"",""sh""]"
powershell,PowerShell,language,"[""powershell"",""pwsh""]"
react,React,frontend,"[""react"",""reactjs"",""react.js""]"
nextjs,Next.js,frontend,"[""next.js"",""nextjs""]"
vue,Vue,frontend,"[""vue"",""vuejs"",""vue.js""]"
angular,Angular,frontend,"[""angular"",""angularjs""]"
tailwind,Tailwind CSS,frontend,"[""tailwind"",""tailwindcss""]"
html,HTML,frontend,"[""html"",""html5""]"
css,CSS,frontend,"[""css"",""css3""]"
nodejs,Node.js,backend,"[""nodejs"",""node.js"",""node js"",""node""]"
express,Express,backend,"[""express"",""expressjs""]"
fastapi,FastAPI,backend,"[""fastapi""]"
flask,Flask,backend,"[""flask""]"
django,Django,backend,"[""django""]"
aspnet-core,ASP.NET Core,backend,"[""asp.net core"",""aspnet core"",""dotnet core""]"
aspnet-mvc,ASP.NET MVC,backend,"[""asp.net mvc"",""aspnet mvc""]"
spring-boot,Spring Boot,backend,"[""spring boot"",""springboot""]"
ef-core,Entity Framework Core,backend,"[""entity framework core"",""ef core""]"
graphql,GraphQL,backend,"[""graphql""]"
rest-api,REST API,backend,"[""rest"",""rest api"",""restful""]"
grpc,gRPC,backend,"[""grpc""]"
microservices,Microservices,architecture,"[""microservices"",""microservice""]"
serverless,Serverless,architecture,"[""serverless""]"
event-driven,Event-Driven Architecture,architecture,"[""event driven"",""eda""]"
ddd,Domain-Driven Design,architecture,"[""ddd"",""domain driven design""]"
postgresql,PostgreSQL,database,"[""postgresql"",""postgres""]"
mysql,MySQL,database,"[""mysql""]"
sqlserver,SQL Server,database,"[""sql server"",""mssql""]"
mongodb,MongoDB,database,"[""mongodb""]"
redis,Redis,database,"[""redis""]"
dynamodb,DynamoDB,database,"[""dynamodb""]"
elasticsearch,Elasticsearch,database,"[""elasticsearch"",""elastic search""]"
opensearch,OpenSearch,database,"[""opensearch""]"
duckdb,DuckDB,database,"[""duckdb""]"
clickhouse,ClickHouse,database,"[""clickhouse""]"
snowflake,Snowflake,database,"[""snowflake""]"
aws,AWS,cloud,"[""aws"",""amazon web services""]"
aws-lambda,AWS Lambda,cloud,"[""lambda"",""aws lambda""]"
aws-api-gateway,AWS API Gateway,cloud,"[""api gateway"",""aws api gateway""]"
aws-s3,AWS S3,cloud,"[""s3"",""aws s3""]"
aws-rds,AWS RDS,cloud,"[""rds"",""aws rds""]"
aws-ec2,AWS EC2,cloud,"[""ec2"",""aws ec2""]"
aws-ecs,AWS ECS,cloud,"[""ecs"",""aws ecs""]"
aws-eks,AWS EKS,cloud,"[""eks"",""aws eks""]"
aws-cloudformation,AWS CloudFormation,cloud,"[""cloudformation"",""cfn""]"
aws-cdk,AWS CDK,cloud,"[""cdk"",""aws cdk""]"
bedrock,Amazon Bedrock,ai,"[""bedrock"",""amazon bedrock""]"
gcp,GCP,cloud,"[""gcp"",""google cloud""]"
azure,Azure,cloud,"[""azure"",""ms azure""]"
docker,Docker,devops,"[""docker""]"
kubernetes,Kubernetes,devops,"[""kubernetes"",""k8s"",""kube""]"
terraform,Terraform,devops,"[""terraform""]"
helm,Helm,devops,"[""helm""]"
ansible,Ansible,devops,"[""ansible""]"
github-actions,GitHub Actions,devops,"[""github actions"",""gh actions""]"
gitlab-ci,GitLab CI,devops,"[""gitlab ci"",""gitlab-ci""]"
jenkins,Jenkins,devops,"[""jenkins""]"
git,Git,devops,"[""git""]"
linux,Linux,devops,"[""linux""]"
nginx,nginx,devops,"[""nginx""]"
kafka,Kafka,messaging,"[""kafka""]"
rabbitmq,RabbitMQ,messaging,"[""rabbitmq""]"
sqs,AWS SQS,messaging,"[""sqs"",""aws sqs""]"
sns,AWS SNS,messaging,"[""sns"",""aws sns""]"
jwt-auth,JWT Auth,security,"[""jwt"",""jwt auth"",""jwt authentication""]"
oauth2,OAuth 2.0,security,"[""oauth"",""oauth2""]"
pytest,pytest,testing,"[""pytest""]"
jest,Jest,testing,"[""jest""]"
playwright,Playwright,testing,"[""playwright""]"
selenium,Selenium,testing,"[""selenium""]"
rag,RAG,ai,"[""rag"",""retrieval augmented generation""]"
prompt-engineering,Prompt Engineering,ai,"[""prompt engineering""]"
langchain,LangChain,ai,"[""langchain""]"
openai-api,OpenAI API,ai,"[""openai""]"
gemini-api,Gemini API,ai,"[""gemini"",""google gemini""]"
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/db/seed_skills.csv
git commit -m "feat(db): seed_skills.csv with 80 canonical tech skills"
```

### Task 2.5: db/repo.py — upserts, queries, seeding

**Files:**
- Create: `jobscope/db/repo.py`
- Test: `tests/db/test_repo.py`

- [ ] **Step 1: Write failing test**

```python
# tests/db/test_repo.py
from datetime import datetime, timezone
from jobscope.db import repo
from jobscope.db.connection import open_rw, init_schema

def _conn(tmp_path):
    c = open_rw(tmp_path / "t.duckdb"); init_schema(c); return c

def test_seed_skills_loads_rows(tmp_path):
    c = _conn(tmp_path)
    n = repo.seed_skills_canonical(c)
    assert n >= 80
    row = c.execute("SELECT display_name FROM skills_canonical WHERE skill_canonical='python'").fetchone()
    assert row[0] == "Python"

def test_start_session_inserts_and_sets_pointer(tmp_path):
    c = _conn(tmp_path)
    sid = repo.start_session(c, ["AWS Engineer"], "Bengaluru")
    row = c.execute("SELECT session_id FROM sessions WHERE session_id=?", [sid]).fetchone()
    assert row is not None
    ptr = c.execute("SELECT current_session_id FROM session_state WHERE id=1").fetchone()[0]
    assert ptr == sid

def test_upsert_job_is_idempotent(tmp_path):
    c = _conn(tmp_path)
    sid = repo.start_session(c, ["X"], "X")
    job = {"job_id": "1", "session_id": sid, "scraped_at": datetime.now(timezone.utc),
           "search_term": "X", "title": "T", "company": "C", "location": "L",
           "work_style": "Remote", "posted_relative": "1d", "experience_text": "3-5 yrs",
           "experience_min": 3, "experience_max": 5, "salary_min_lpa": None,
           "salary_max_lpa": None, "salary_text": None,
           "jd_full_text": "long jd", "jd_url": "https://x"}
    repo.upsert_job(c, job)
    repo.upsert_job(c, job)
    n = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert n == 1

def test_record_decision_persists(tmp_path):
    c = _conn(tmp_path)
    sid = repo.start_session(c, ["X"], "X")
    repo.upsert_job(c, {"job_id": "j", "session_id": sid, "scraped_at": datetime.now(timezone.utc),
                        "search_term": "X", "title": "T", "company": "C", "location": "L",
                        "work_style": None, "posted_relative": None, "experience_text": None,
                        "experience_min": None, "experience_max": None, "salary_min_lpa": None,
                        "salary_max_lpa": None, "salary_text": None,
                        "jd_full_text": "", "jd_url": ""})
    repo.record_decision(c, job_id="j", session_id=sid, decision="apply", source="user")
    row = c.execute("SELECT decision, source FROM decisions WHERE job_id='j'").fetchone()
    assert row == ("apply", "user")
```

- [ ] **Step 2: Run test, confirm failure**

```bash
pytest tests/db/test_repo.py -v
```

- [ ] **Step 3: Implement repo.py**

```python
# jobscope/db/repo.py
"""DuckDB write/read helpers. All functions take a connection."""
from __future__ import annotations
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import duckdb
from jobscope.utils.ids import new_session_id, new_uuid

SEED_CSV = Path(__file__).parent / "seed_skills.csv"

# ---------- skills ----------

def seed_skills_canonical(conn: duckdb.DuckDBPyConnection) -> int:
    """Idempotent upsert of seed_skills.csv into skills_canonical."""
    with SEED_CSV.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    n = 0
    for r in rows:
        conn.execute("""
            INSERT INTO skills_canonical(skill_canonical, display_name, category, aliases)
            VALUES (?, ?, ?, ?::JSON)
            ON CONFLICT(skill_canonical) DO UPDATE SET
              display_name = excluded.display_name,
              category     = excluded.category,
              aliases      = excluded.aliases
        """, [r["skill_canonical"], r["display_name"], r["category"], r["aliases"]])
        n += 1
    return n

# ---------- sessions ----------

def start_session(conn, search_terms: list[str], search_location: str,
                  filters: dict | None = None) -> str:
    sid = new_session_id()
    conn.execute("""
        INSERT INTO sessions(session_id, started_at, search_terms, search_location, filters_applied)
        VALUES (?, ?, ?::JSON, ?, ?::JSON)
    """, [sid, datetime.now(timezone.utc), json.dumps(search_terms),
          search_location, json.dumps(filters or {})])
    conn.execute("""
        UPDATE session_state SET current_session_id=?, last_active_at=? WHERE id=1
    """, [sid, datetime.now(timezone.utc)])
    return sid

def end_session(conn, session_id: str, reason: str) -> None:
    conn.execute("""
        UPDATE sessions SET ended_at=?, ended_reason=? WHERE session_id=?
    """, [datetime.now(timezone.utc), reason, session_id])

def touch_current_job(conn, job_id: str) -> None:
    conn.execute("""
        UPDATE session_state SET current_job_id=?, last_active_at=? WHERE id=1
    """, [job_id, datetime.now(timezone.utc)])

# ---------- jobs ----------

def upsert_job(conn, job: dict[str, Any]) -> None:
    cols = ["job_id","session_id","scraped_at","search_term","title","company","location",
            "work_style","posted_relative","experience_text","experience_min","experience_max",
            "salary_min_lpa","salary_max_lpa","salary_text","jd_full_text","jd_url"]
    placeholders = ",".join(["?"] * len(cols))
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "job_id")
    conn.execute(f"""
        INSERT INTO jobs({",".join(cols)}) VALUES ({placeholders})
        ON CONFLICT(job_id) DO UPDATE SET {updates}
    """, [job.get(c) for c in cols])

def mark_job_status(conn, job_id: str, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE jobs SET analysis_status=?, analysis_error=? WHERE job_id=?",
        [status, error, job_id],
    )

# ---------- analyses ----------

def insert_analysis(conn, *, job_id: str, prompt_version: str, model_name: str,
                    latency_ms: int, parsed: dict, raw_json: str) -> str:
    aid = new_uuid()
    conn.execute("""
        INSERT INTO analyses(analysis_id, job_id, prompt_version, model_name,
                             analyzed_at, latency_ms, fit_score, experience_verdict,
                             jd_quality, red_flags, recommendation, resume_tailoring,
                             raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?, ?, ?::JSON)
    """, [aid, job_id, prompt_version, model_name,
          datetime.now(timezone.utc), latency_ms,
          parsed["fit_score"], parsed["experience_verdict"], parsed["jd_quality"],
          json.dumps(parsed.get("red_flags", [])),
          parsed["recommendation"], parsed["resume_tailoring"], raw_json])
    return aid

def replace_job_skills(conn, job_id: str, skills: list[dict]) -> None:
    """Replace all skills for one job atomically."""
    conn.execute("DELETE FROM job_skills WHERE job_id=?", [job_id])
    for s in skills:
        conn.execute("""
            INSERT INTO job_skills(job_id, skill_canonical, skill_as_written, kind)
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
        """, [job_id, s["canonical"], s["as_written"], s["kind"]])

# ---------- decisions ----------

def record_decision(conn, *, job_id: str, session_id: str, decision: str,
                    source: str, notes: str | None = None) -> str:
    did = new_uuid()
    conn.execute("""
        INSERT INTO decisions(decision_id, job_id, session_id, decided_at,
                              decision, source, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [did, job_id, session_id, datetime.now(timezone.utc), decision, source, notes])
    return did

# ---------- user profile ----------

def upsert_user_profile(conn, profile: dict) -> None:
    conn.execute("""
        INSERT INTO user_profile(id, full_name, current_role, current_company,
                                 experience_years, current_ctc_lpa, expected_ctc_lpa,
                                 current_location, willing_locations, certifications,
                                 updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?::JSON, ?)
        ON CONFLICT(id) DO UPDATE SET
          full_name=excluded.full_name, current_role=excluded.current_role,
          current_company=excluded.current_company,
          experience_years=excluded.experience_years,
          current_ctc_lpa=excluded.current_ctc_lpa,
          expected_ctc_lpa=excluded.expected_ctc_lpa,
          current_location=excluded.current_location,
          willing_locations=excluded.willing_locations,
          certifications=excluded.certifications,
          updated_at=excluded.updated_at
    """, [profile.get("full_name"), profile.get("current_role"),
          profile.get("current_company"), profile.get("experience_years"),
          profile.get("current_ctc_lpa"), profile.get("expected_ctc_lpa"),
          profile.get("current_location"),
          json.dumps(profile.get("willing_locations", [])),
          json.dumps(profile.get("certifications", [])),
          datetime.now(timezone.utc)])

def replace_user_skills(conn, skills: list[dict]) -> None:
    conn.execute("DELETE FROM user_skills")
    for s in skills:
        conn.execute("""
            INSERT INTO user_skills(skill_canonical, proficiency, years)
            VALUES (?, ?, ?)
        """, [s["skill_canonical"], s.get("proficiency"), s.get("years")])
```

- [ ] **Step 4: Run test, confirm pass**

```bash
pytest tests/db/test_repo.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/db/repo.py tests/db/test_repo.py
git commit -m "feat(db): repo with upserts, session lifecycle, skill seed"
```

### Task 2.6: View smoke test

**Files:**
- Test: `tests/db/test_views.py`

- [ ] **Step 1: Write a view-smoke test**

```python
# tests/db/test_views.py
from datetime import datetime, timezone
from jobscope.db import repo
from jobscope.db.connection import open_rw, init_schema

def _seed(tmp_path):
    c = open_rw(tmp_path / "v.duckdb"); init_schema(c)
    repo.seed_skills_canonical(c)
    repo.replace_user_skills(c, [{"skill_canonical": "python", "proficiency": "expert", "years": 3}])
    sid = repo.start_session(c, ["AWS Engineer"], "Bengaluru")
    repo.upsert_job(c, {"job_id":"j1","session_id":sid,"scraped_at":datetime.now(timezone.utc),
                        "search_term":"AWS Engineer","title":"Sr AWS Eng","company":"Acme",
                        "location":"BLR","work_style":"Remote","posted_relative":"1d",
                        "experience_text":"3-5","experience_min":3,"experience_max":5,
                        "salary_min_lpa":None,"salary_max_lpa":None,"salary_text":None,
                        "jd_full_text":"need kubernetes","jd_url":"u"})
    repo.replace_job_skills(c, "j1", [
        {"canonical":"kubernetes","as_written":"K8s","kind":"required"},
        {"canonical":"python","as_written":"Python","kind":"required"},
    ])
    repo.insert_analysis(c, job_id="j1", prompt_version="1.0.0",
        model_name="gemini-2.5-flash-lite", latency_ms=2000,
        parsed={"fit_score":70,"experience_verdict":"in_range","jd_quality":"average",
                "red_flags":[],"recommendation":"ok","resume_tailoring":"emphasize python"},
        raw_json='{"ok":true}')
    repo.record_decision(c, job_id="j1", session_id=sid, decision="apply", source="user")
    return c, sid

def test_v_job_analysis_returns_joined_row(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute("SELECT title, fit_score, latest_decision FROM v_job_analysis").fetchone()
    assert row == ("Sr AWS Eng", 70, "apply")

def test_v_skill_gaps_flags_missing_kubernetes(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute(
        "SELECT jobs_where_missing FROM v_skill_gaps WHERE skill_canonical='kubernetes'"
    ).fetchone()
    assert row[0] == 1

def test_v_skill_gaps_does_not_flag_python_user_has_it(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute(
        "SELECT jobs_where_missing FROM v_skill_gaps WHERE skill_canonical='python'"
    ).fetchone()
    assert row[0] == 0

def test_v_current_session_stats(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute(
        "SELECT jobs_evaluated, applied, avg_fit FROM v_current_session_stats"
    ).fetchone()
    assert row == (1, 1, 70.0)
```

- [ ] **Step 2: Run, confirm pass**

```bash
pytest tests/db/test_views.py -v
```
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/db/test_views.py
git commit -m "test(db): smoke tests for v_job_analysis / v_skill_gaps / v_current_session_stats"
```

---

---

## Phase 3 — Profile pipeline

### Task 3.1: Copy resume PDF into project

**Files:**
- Copy: `auto_job_applier_linkedIn/config/Rajarshi_Bose_Resume_2026-05-13.pdf` → `projects/jobscope/resume.pdf`

- [ ] **Step 1: Make project dir and copy**

```bash
mkdir -p projects/jobscope/state
cp "auto_job_applier_linkedIn/config/Rajarshi_Bose_Resume_2026-05-13.pdf" projects/jobscope/resume.pdf
```

- [ ] **Step 2: Commit**

```bash
git add projects/jobscope/resume.pdf
git commit -m "chore(profile): copy resume PDF into project root"
```

### Task 3.2: profile/parse_resume.py — extract text from PDF

**Files:**
- Create: `jobscope/profile/parse_resume.py`
- Test: `tests/test_parse_resume.py`

Note: Jetro's `jet_parse` tool is not callable from Python — it's an MCP tool. For the Python pipeline we use `pdfplumber` (lightweight, no native deps). Add it to deps.

- [ ] **Step 1: Add pdfplumber to deps**

Edit `pyproject.toml`, append to dependencies:
```
  "pdfplumber>=0.11",
```

Run: `pip install -e ".[dev]"`

- [ ] **Step 2: Write failing test**

```python
# tests/test_parse_resume.py
from pathlib import Path
from jobscope.profile.parse_resume import extract_text

def test_extract_text_returns_nonempty_for_real_resume():
    pdf = Path("projects/jobscope/resume.pdf")
    if not pdf.exists():
        import pytest; pytest.skip("resume.pdf not present")
    text = extract_text(pdf)
    assert len(text) > 500
    assert "Rajarshi" in text or "Bose" in text
```

- [ ] **Step 3: Run test, confirm failure**

```bash
pytest tests/test_parse_resume.py -v
```

- [ ] **Step 4: Implement parse_resume.py**

```python
# jobscope/profile/parse_resume.py
"""Resume PDF → raw text. Downstream `normalize` turns text into profile dict."""
from pathlib import Path
import pdfplumber

def extract_text(pdf_path: Path) -> str:
    out = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            out.append(t)
    return "\n".join(out)
```

- [ ] **Step 5: Run test, confirm pass**

```bash
pytest tests/test_parse_resume.py -v
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml jobscope/profile/parse_resume.py tests/test_parse_resume.py
git commit -m "feat(profile): pdfplumber-based resume text extraction"
```

### Task 3.3: profile/normalize.py — write profile.json + sync DB

**Files:**
- Create: `jobscope/profile/normalize.py`
- Create: `projects/jobscope/profile.json` (committed)
- Test: `tests/test_profile_normalize.py`

The profile is hand-authored once (data already known from spec). The
`normalize` module loads `profile.json`, validates it, and syncs to DuckDB.
PDF parsing is for sanity check only (verifies the PDF still parses).

- [ ] **Step 1: Author projects/jobscope/profile.json**

```json
{
  "full_name": "Rajarshi Bose",
  "current_role": "Full-Stack Developer (Solutions)",
  "current_company": "Tecnomic Systems",
  "experience_years": 2.0,
  "current_ctc_lpa": 7.5,
  "expected_ctc_lpa": 12.0,
  "current_location": "Bangalore",
  "willing_locations": ["Bangalore", "Chennai", "Remote"],
  "certifications": [
    "AWS Solutions Architect Associate",
    "AWS Developer Associate",
    "AWS AI Practitioner",
    "AWS Cloud Practitioner"
  ],
  "skills": [
    {"skill_canonical": "csharp",            "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "aspnet-core",       "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "aspnet-mvc",        "proficiency": "proficient", "years": 1.5},
    {"skill_canonical": "react",             "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "python",            "proficiency": "proficient", "years": 2.0},
    {"skill_canonical": "sql",               "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "javascript",        "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "postgresql",        "proficiency": "proficient", "years": 1.0},
    {"skill_canonical": "dynamodb",          "proficiency": "proficient", "years": 1.0},
    {"skill_canonical": "mysql",             "proficiency": "familiar",   "years": 0.5},
    {"skill_canonical": "aws",               "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "aws-lambda",        "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "aws-api-gateway",   "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "aws-s3",            "proficiency": "proficient", "years": 1.5},
    {"skill_canonical": "aws-rds",           "proficiency": "proficient", "years": 1.5},
    {"skill_canonical": "opensearch",        "proficiency": "familiar",   "years": 0.5},
    {"skill_canonical": "aws-cloudformation","proficiency": "proficient", "years": 1.0},
    {"skill_canonical": "bedrock",           "proficiency": "proficient", "years": 1.0},
    {"skill_canonical": "rag",               "proficiency": "proficient", "years": 1.0},
    {"skill_canonical": "prompt-engineering","proficiency": "proficient", "years": 1.0},
    {"skill_canonical": "rest-api",          "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "jwt-auth",          "proficiency": "proficient", "years": 1.5},
    {"skill_canonical": "ef-core",           "proficiency": "proficient", "years": 1.5},
    {"skill_canonical": "serverless",        "proficiency": "expert",     "years": 2.0},
    {"skill_canonical": "microservices",     "proficiency": "proficient", "years": 1.0},
    {"skill_canonical": "git",               "proficiency": "expert",     "years": 2.0}
  ],
  "projects": [
    {
      "name": "Admin UI for Amazon Connect",
      "stack": ["aspnet-core", "aspnet-mvc", "react", "aws-lambda", "aws-api-gateway"],
      "summary": "Internal admin tool for Amazon Connect contact center operations"
    },
    {
      "name": "Gen AI Chatbot with Bedrock Agents",
      "stack": ["bedrock", "rag", "aws-lambda", "react", "prompt-engineering"],
      "summary": "RAG-based assistant using Bedrock Agents + Lambda backend"
    },
    {
      "name": "Chrome Extension for JS Automation",
      "stack": ["javascript", "html", "css"],
      "summary": "Browser extension for automating repetitive web workflows"
    }
  ]
}
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_profile_normalize.py
from pathlib import Path
from jobscope.profile.normalize import load_profile, sync_profile_to_db
from jobscope.db.connection import open_rw, init_schema

def test_load_profile_returns_dict(tmp_path):
    p = load_profile(Path("projects/jobscope/profile.json"))
    assert p["full_name"] == "Rajarshi Bose"
    assert len(p["skills"]) > 20

def test_sync_profile_to_db_populates_tables(tmp_path):
    p = load_profile(Path("projects/jobscope/profile.json"))
    c = open_rw(tmp_path / "p.duckdb"); init_schema(c)
    sync_profile_to_db(c, p)
    name = c.execute("SELECT full_name FROM user_profile WHERE id=1").fetchone()[0]
    assert name == "Rajarshi Bose"
    n = c.execute("SELECT COUNT(*) FROM user_skills").fetchone()[0]
    assert n == len(p["skills"])
```

- [ ] **Step 3: Run test, confirm failure**

```bash
pytest tests/test_profile_normalize.py -v
```

- [ ] **Step 4: Implement normalize.py**

```python
# jobscope/profile/normalize.py
"""Load and validate profile.json; sync to DuckDB user_profile/user_skills."""
import json
from pathlib import Path
import duckdb
from jobscope.db import repo

REQUIRED = {"full_name", "experience_years", "expected_ctc_lpa", "skills"}

def load_profile(profile_path: Path) -> dict:
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    missing = REQUIRED - set(data.keys())
    if missing:
        raise ValueError(f"profile.json missing required keys: {missing}")
    if not isinstance(data["skills"], list) or not data["skills"]:
        raise ValueError("profile.skills must be a non-empty list")
    return data

def sync_profile_to_db(conn: duckdb.DuckDBPyConnection, profile: dict) -> None:
    repo.upsert_user_profile(conn, profile)
    repo.replace_user_skills(conn, profile["skills"])
```

- [ ] **Step 5: Run test, confirm pass**

```bash
pytest tests/test_profile_normalize.py -v
```

- [ ] **Step 6: Commit**

```bash
git add jobscope/profile/normalize.py projects/jobscope/profile.json tests/test_profile_normalize.py
git commit -m "feat(profile): load profile.json, sync user_profile/user_skills to DuckDB"
```

---

## Phase 4 — AI module (schema, prompts, client, analyzer)

### Task 4.1: ai/schema.py — Pydantic models

**Files:**
- Create: `jobscope/ai/schema.py`
- Test: `tests/ai/test_schema.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ai/test_schema.py
import pytest
from pydantic import ValidationError
from jobscope.ai.schema import JobAnalysis

GOOD = {
    "fit_score": 70, "fit_rationale": "ok",
    "experience_verdict": "in_range",
    "experience_min_years": 2, "experience_max_years": 4,
    "skills": [{"canonical": "python", "as_written": "Python", "kind": "required"}],
    "red_flags": [],
    "jd_quality": "average",
    "recommendation": "decent fit",
    "resume_tailoring": "emphasize python",
    "salary_min_lpa": None, "salary_max_lpa": None,
}

def test_accepts_valid_payload():
    a = JobAnalysis.model_validate(GOOD)
    assert a.fit_score == 70

def test_rejects_out_of_range_fit_score():
    bad = {**GOOD, "fit_score": 120}
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(bad)

def test_rejects_unknown_red_flag_kind():
    bad = {**GOOD, "red_flags": [{"kind": "bogus", "text": "x"}]}
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(bad)

def test_rejects_unknown_skill_kind():
    bad = {**GOOD, "skills": [{"canonical": "x", "as_written": "X", "kind": "matched"}]}
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(bad)
```

- [ ] **Step 2: Run, confirm failure**

```bash
pytest tests/ai/test_schema.py -v
```

- [ ] **Step 3: Implement schema.py**

```python
# jobscope/ai/schema.py
"""Pydantic models for the Gemini response contract."""
from typing import Literal, Optional
from pydantic import BaseModel, Field

RedFlagKind = Literal[
    "staffing_recruiting", "experience_mismatch", "skill_domain_mismatch",
    "visa_or_citizenship", "salary_below_expected", "vague_jd",
]

class RedFlag(BaseModel):
    kind: RedFlagKind
    text: str

class JDSkill(BaseModel):
    canonical: str
    as_written: str
    kind: Literal["required", "nice_to_have"]

class JobAnalysis(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    fit_rationale: str
    experience_verdict: Literal["in_range", "under", "over", "way_over"]
    experience_min_years: Optional[int] = None
    experience_max_years: Optional[int] = None
    skills: list[JDSkill]
    red_flags: list[RedFlag] = []
    jd_quality: Literal["well_written", "average", "vague"]
    recommendation: str
    resume_tailoring: str
    salary_min_lpa: Optional[float] = None
    salary_max_lpa: Optional[float] = None
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/ai/test_schema.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/ai/schema.py tests/ai/test_schema.py
git commit -m "feat(ai): Pydantic JobAnalysis schema with literal-constrained fields"
```

### Task 4.2: ai/prompts.py — system prompt + user-message builder

**Files:**
- Create: `jobscope/ai/prompts.py`

- [ ] **Step 1: Write prompts.py**

```python
# jobscope/ai/prompts.py
"""Prompt templates for the per-job Gemini call."""
from __future__ import annotations
import json

PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """\
You are JobScope's job-fit analyst. You evaluate ONE LinkedIn job listing
for ONE specific candidate and produce a structured JSON analysis.

Your job is NOT to be encouraging or to "find positives." Be honest.
A 45 means 45. Bad fits stay bad fits.

CANDIDATE PROFILE
{profile_json}

KNOWN SKILL CANONICAL NAMES — use these slugs when you recognize a skill;
invent slug-case names like "spring-boot" only if a skill isn't in this list:
{skills_canonical_csv}

INSTRUCTIONS
1. Read the job listing below.
2. Extract required + nice-to-have skills. Map each to a canonical slug.
   The JSON only stores required vs nice_to_have; SQL computes matched/missing
   against the candidate's skills.
3. Classify the experience requirement vs candidate's years.
4. Identify red flags from this exact list (use the literal kinds):
   - staffing_recruiting: company is a staffing/recruiting firm
   - experience_mismatch: requirement >= candidate_years + 4
   - skill_domain_mismatch: >50% of required skills are outside candidate's domain
   - visa_or_citizenship: requires citizenship/visa candidate lacks
   - salary_below_expected: stated salary clearly below candidate's expected CTC
   - vague_jd: JD is buzzword-stuffed with no concrete tech stack
5. Score fit 0-100. Rubric:
   - 80-100 strong fit (apply)
   - 60-79  decent fit (apply with tailoring)
   - 40-59  stretch
   - 20-39  weak (skip unless desperate)
   - 0-19   reject (wrong domain entirely)
   Weighting: skills overlap 50% / experience match 25% / red flags 25%.
   "experience_mismatch" caps score at 40. "skill_domain_mismatch" caps at 30.
6. Write fit_rationale BEFORE settling on the score (1 short paragraph).
7. recommendation: 2-3 honest sentences.
8. resume_tailoring: 1-2 sentences. MUST reference at least one project name
   from the candidate's projects list.
9. Rate JD quality: well_written / average / vague.

OUTPUT: ONLY the JSON object matching the schema. No prose, no markdown.
"""

USER_TEMPLATE = """\
JOB LISTING

Title:        {title}
Company:      {company}
Location:     {location}
Work style:   {work_style}
Posted:       {posted_relative}
Experience:   {experience_text}

DESCRIPTION
{jd_full_text}
"""

def build_system(profile: dict, skills_canonical: list[str]) -> str:
    return SYSTEM_PROMPT.format(
        profile_json=json.dumps(profile, indent=2),
        skills_canonical_csv=", ".join(sorted(skills_canonical)),
    )

def build_user(job: dict) -> str:
    return USER_TEMPLATE.format(
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        work_style=job.get("work_style", "") or "",
        posted_relative=job.get("posted_relative", "") or "",
        experience_text=job.get("experience_text", "") or "",
        jd_full_text=job.get("jd_full_text", "") or "",
    )
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/ai/prompts.py
git commit -m "feat(ai): system + user prompt templates with profile and skill injection"
```

### Task 4.3: ai/client.py — Gemini client with key rotation

**Files:**
- Create: `jobscope/ai/client.py`
- Test: `tests/ai/test_client.py`

- [ ] **Step 1: Write failing test (mocked SDK)**

```python
# tests/ai/test_client.py
import pytest
from unittest.mock import MagicMock, patch
from jobscope.ai.client import GeminiClient, RateLimitError, AnalysisFailure

def test_rotates_on_429():
    keys = ["k1", "k2", "k3"]
    client = GeminiClient(keys=keys, model="m")
    # First call rate-limits, second succeeds
    fake = MagicMock()
    fake.text = '{"ok": true}'
    side = [RateLimitError("429"), fake]
    with patch.object(client, "_call_once", side_effect=side) as call_once:
        out = client.generate_json(system="s", user="u", response_schema=dict)
    assert out.text == '{"ok": true}'
    assert call_once.call_count == 2
    # Key cycled
    assert client._current_key == "k2"

def test_raises_after_all_keys_429():
    keys = ["k1", "k2"]
    client = GeminiClient(keys=keys, model="m")
    with patch.object(client, "_call_once", side_effect=RateLimitError("429")):
        with pytest.raises(AnalysisFailure) as ei:
            client.generate_json(system="s", user="u", response_schema=dict)
    assert "exhausted" in str(ei.value).lower()
```

- [ ] **Step 2: Run, confirm failure**

```bash
pytest tests/ai/test_client.py -v
```

- [ ] **Step 3: Implement client.py**

```python
# jobscope/ai/client.py
"""Thin wrapper around google-genai SDK with multi-key rotation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from google import genai
from google.genai import types as gtypes
from jobscope import config

class RateLimitError(Exception):
    """Provider signalled 429 / quota exhausted for the current key."""

class AnalysisFailure(Exception):
    """Unrecoverable failure across all retries."""

@dataclass
class GeminiResult:
    text: str

class GeminiClient:
    def __init__(self, keys: list[str], model: str):
        if not keys:
            raise ValueError("GeminiClient requires at least one API key")
        self._keys = keys
        self._idx = 0
        self._current_key = keys[0]
        self._model = model
        self._client = genai.Client(api_key=self._current_key)

    def _rotate(self) -> bool:
        """Move to next key. Returns False if we've cycled through all."""
        self._idx += 1
        if self._idx >= len(self._keys):
            return False
        self._current_key = self._keys[self._idx]
        self._client = genai.Client(api_key=self._current_key)
        return True

    def _call_once(self, system: str, user: str, response_schema) -> GeminiResult:
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=user,
                config=gtypes.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=config.GEMINI_TEMPERATURE,
                ),
            )
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "quota" in msg or "rate" in msg:
                raise RateLimitError(str(e)) from e
            raise
        return GeminiResult(text=resp.text)

    def generate_json(self, *, system: str, user: str, response_schema: Any) -> GeminiResult:
        """Call Gemini; rotate keys on 429; surface RateLimitError exhaustion."""
        attempts = 0
        while True:
            attempts += 1
            try:
                return self._call_once(system, user, response_schema)
            except RateLimitError:
                if not self._rotate():
                    raise AnalysisFailure(
                        f"All Gemini API keys exhausted after {attempts} attempts"
                    )
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/ai/test_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/ai/client.py tests/ai/test_client.py
git commit -m "feat(ai): GeminiClient with key rotation on 429"
```

### Task 4.4: ai/analyzer.py — single-job orchestration

**Files:**
- Create: `jobscope/ai/analyzer.py`
- Test: `tests/ai/test_analyzer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ai/test_analyzer.py
import json
from unittest.mock import MagicMock
import pytest
from jobscope.ai.analyzer import analyze
from jobscope.ai.client import AnalysisFailure

VALID_JSON = json.dumps({
    "fit_score": 65, "fit_rationale": "decent",
    "experience_verdict": "in_range",
    "experience_min_years": 2, "experience_max_years": 4,
    "skills": [{"canonical": "python", "as_written": "Python", "kind": "required"}],
    "red_flags": [],
    "jd_quality": "average",
    "recommendation": "ok",
    "resume_tailoring": "emphasize python",
    "salary_min_lpa": None, "salary_max_lpa": None,
})

def _client(text_seq):
    c = MagicMock()
    results = [MagicMock(text=t) for t in text_seq]
    c.generate_json.side_effect = results
    return c

def test_analyze_returns_parsed_and_raw():
    c = _client([VALID_JSON])
    profile = {"full_name": "x"}; canon = ["python"]
    job = {"title": "T"}
    parsed, raw, latency = analyze(c, profile=profile, skills_canonical=canon, job=job)
    assert parsed.fit_score == 65
    assert raw == VALID_JSON
    assert latency >= 0

def test_analyze_retries_once_on_invalid_json():
    c = _client(["not json", VALID_JSON])
    parsed, _, _ = analyze(c, profile={}, skills_canonical=[], job={})
    assert parsed.fit_score == 65
    assert c.generate_json.call_count == 2

def test_analyze_fails_after_two_invalid_responses():
    c = _client(["not json", "still not"])
    with pytest.raises(AnalysisFailure):
        analyze(c, profile={}, skills_canonical=[], job={})
```

- [ ] **Step 2: Run, confirm failure**

```bash
pytest tests/ai/test_analyzer.py -v
```

- [ ] **Step 3: Implement analyzer.py**

```python
# jobscope/ai/analyzer.py
"""Single-job analysis with one retry on parse/validation failure."""
from __future__ import annotations
import json
import time
from typing import Tuple
from pydantic import ValidationError
from jobscope.ai.client import GeminiClient, AnalysisFailure
from jobscope.ai.prompts import build_system, build_user
from jobscope.ai.schema import JobAnalysis

def analyze(
    client: GeminiClient,
    *,
    profile: dict,
    skills_canonical: list[str],
    job: dict,
) -> Tuple[JobAnalysis, str, int]:
    """Return (parsed, raw_json_text, latency_ms). Raises AnalysisFailure on hard fail."""
    system = build_system(profile, skills_canonical)
    user = build_user(job)
    last_err: Exception | None = None
    for attempt in (1, 2):
        t0 = time.monotonic()
        result = client.generate_json(system=system, user=user, response_schema=JobAnalysis)
        latency_ms = int((time.monotonic() - t0) * 1000)
        try:
            parsed = JobAnalysis.model_validate_json(result.text)
            return parsed, result.text, latency_ms
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = e
            if attempt == 2:
                break
    raise AnalysisFailure(f"validation failed twice: {last_err}")
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/ai/test_analyzer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/ai/analyzer.py tests/ai/test_analyzer.py
git commit -m "feat(ai): per-job analyzer with one retry on validation failure"
```

---

---

## Phase 5 — Scraper

Selectors and patterns lifted from `auto_job_applier_linkedIn/runAiBot.py` and
`auto_job_applier_linkedIn/modules/clickers_and_finders.py`. We adapt them into
tighter modules with type hints and explicit waits.

### Task 5.1: scraper/_clickers.py — wait/click helpers

**Files:**
- Create: `jobscope/scraper/_clickers.py`

Reference: `auto_job_applier_linkedIn/modules/clickers_and_finders.py` —
copy the underlying patterns (WebDriverWait, expected_conditions, retries).
We do NOT import from the reference; we re-author the helpers we use.

- [ ] **Step 1: Implement clickers**

```python
# jobscope/scraper/_clickers.py
"""Safe wait/click helpers. Adapted from the reference's clickers_and_finders.py."""
from __future__ import annotations
import time
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, ElementClickInterceptedException,
    StaleElementReferenceException, NoSuchElementException,
)

def wait_for(driver: WebDriver, by: By, selector: str, timeout: int = 10
             ) -> Optional[WebElement]:
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None

def wait_clickable(driver: WebDriver, by: By, selector: str, timeout: int = 10
                   ) -> Optional[WebElement]:
    try:
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
    except TimeoutException:
        return None

def safe_click(driver: WebDriver, element: WebElement, retries: int = 3) -> bool:
    for _ in range(retries):
        try:
            element.click()
            return True
        except (ElementClickInterceptedException, StaleElementReferenceException):
            time.sleep(0.5)
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                time.sleep(0.5)
    return False

def find_or_none(parent, by: By, selector: str) -> Optional[WebElement]:
    try:
        return parent.find_element(by, selector)
    except NoSuchElementException:
        return None

def text_or_empty(parent, by: By, selector: str) -> str:
    el = find_or_none(parent, by, selector)
    return (el.text or "").strip() if el else ""

def attr_or_empty(parent, by: By, selector: str, attr: str) -> str:
    el = find_or_none(parent, by, selector)
    return (el.get_attribute(attr) or "").strip() if el else ""
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/scraper/_clickers.py
git commit -m "feat(scraper): wait/click/find helpers for selenium"
```

### Task 5.2: scraper/browser.py — undetected-chromedriver setup

**Files:**
- Create: `jobscope/scraper/browser.py`

Reference: `auto_job_applier_linkedIn/modules/open_chrome.py`. Slimmed: no
resume-generator branches, no extension installer toggle UI.

- [ ] **Step 1: Implement browser.py**

```python
# jobscope/scraper/browser.py
"""Chrome bootstrap with undetected-chromedriver."""
from __future__ import annotations
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from jobscope import config
from jobscope.utils.logging import get_logger

log = get_logger("scraper.browser")

def new_driver() -> uc.Chrome:
    """Return a configured undetected-chromedriver Chrome."""
    opts = Options()
    if config.RUN_IN_BACKGROUND:
        opts.add_argument("--headless=new")
    if config.DISABLE_EXTENSIONS:
        opts.add_argument("--disable-extensions")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-notifications")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    log.info("launching_chrome", extra={"stealth": config.STEALTH_MODE,
                                        "headless": config.RUN_IN_BACKGROUND})
    driver = uc.Chrome(options=opts, use_subprocess=True)
    driver.set_page_load_timeout(45)
    return driver

def quit_driver(driver) -> None:
    try:
        driver.quit()
    except Exception:
        pass
```

- [ ] **Step 2: Smoke test manually**

Run: `python -c "from jobscope.scraper.browser import new_driver, quit_driver; d=new_driver(); d.get('https://example.com'); print(d.title); quit_driver(d)"`
Expected: prints "Example Domain", Chrome opens then closes.

- [ ] **Step 3: Commit**

```bash
git add jobscope/scraper/browser.py
git commit -m "feat(scraper): undetected-chromedriver bootstrap"
```

### Task 5.3: scraper/login.py — LinkedIn login

**Files:**
- Create: `jobscope/scraper/login.py`

Reference: `runAiBot.py::login_LN`.

- [ ] **Step 1: Implement login.py**

```python
# jobscope/scraper/login.py
"""LinkedIn login with 2FA/captcha pause support."""
from __future__ import annotations
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope import config
from jobscope.scraper._clickers import wait_for, wait_clickable, safe_click
from jobscope.utils.logging import get_logger

log = get_logger("scraper.login")

class LoginFailure(Exception):
    pass

LOGIN_URL = "https://www.linkedin.com/login"
HOME_URL = "https://www.linkedin.com/feed/"

def is_logged_in(driver: WebDriver) -> bool:
    driver.get(HOME_URL)
    time.sleep(2)
    return "feed" in driver.current_url and "/login" not in driver.current_url

def login(driver: WebDriver, *, on_verification=None) -> None:
    """Log in. If LinkedIn shows captcha/2FA, calls on_verification (a blocking callable)."""
    if is_logged_in(driver):
        log.info("already_logged_in")
        return
    driver.get(LOGIN_URL)
    user_field = wait_for(driver, By.ID, "username", timeout=15)
    pass_field = wait_for(driver, By.ID, "password", timeout=5)
    if not user_field or not pass_field:
        raise LoginFailure("login page didn't load")
    user_field.clear(); user_field.send_keys(config.LINKEDIN_USERNAME)
    pass_field.clear(); pass_field.send_keys(config.LINKEDIN_PASSWORD)
    submit = wait_clickable(driver, By.CSS_SELECTOR, "button[type='submit']", 5)
    if not submit or not safe_click(driver, submit):
        raise LoginFailure("could not click submit")
    time.sleep(4)
    # Detect 2FA/captcha walls
    for _ in range(60):  # up to 5 minutes
        url = driver.current_url
        if "feed" in url and "/login" not in url:
            log.info("login_success")
            return
        if any(x in url for x in ("checkpoint", "challenge", "captcha", "uas/login-submit")):
            log.warning("login_verification_required", extra={"url": url})
            if on_verification:
                on_verification()
            time.sleep(5)
            continue
        time.sleep(5)
    raise LoginFailure(f"login did not complete; last url: {driver.current_url}")
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/scraper/login.py
git commit -m "feat(scraper): LinkedIn login with verification-wall callback"
```

### Task 5.4: scraper/extract.py — JD parsing + years regex

**Files:**
- Create: `jobscope/scraper/extract.py`
- Test: `tests/scraper/test_extract.py`

Reference: `runAiBot.py::extract_years_of_experience`, `get_job_main_details`,
`get_job_description`. The regex is the most-reused piece.

- [ ] **Step 1: Write failing test for years parser**

```python
# tests/scraper/test_extract.py
import pytest
from jobscope.scraper.extract import extract_years

@pytest.mark.parametrize("text, expected", [
    ("3-5 years of experience", (3, 5)),
    ("5+ years required", (5, None)),
    ("Minimum 4 years", (4, None)),
    ("2 to 4 years", (2, 4)),
    ("No experience required", (0, 0)),
    ("Fresh graduate", (0, 0)),
    ("0-2 years", (0, 2)),
    ("at least 7 years", (7, None)),
    ("",                       (None, None)),
    ("nothing relevant here", (None, None)),
])
def test_extract_years(text, expected):
    assert extract_years(text) == expected
```

- [ ] **Step 2: Run, confirm failure**

```bash
pytest tests/scraper/test_extract.py -v
```

- [ ] **Step 3: Implement extract.py (years regex first)**

```python
# jobscope/scraper/extract.py
"""LinkedIn DOM scraping + JD text parsing."""
from __future__ import annotations
import re
import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope.scraper._clickers import wait_for, text_or_empty, attr_or_empty
from jobscope.utils.logging import get_logger

log = get_logger("scraper.extract")

# ---------- years-of-experience parsing ----------

_RX_RANGE = re.compile(r"(\d{1,2})\s*(?:-|to|–|—)\s*(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?)", re.I)
_RX_PLUS  = re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?)", re.I)
_RX_AT_LEAST = re.compile(r"(?:at\s*least|minimum|min\.?)\s*(\d{1,2})\s*(?:years?|yrs?)", re.I)
_RX_NUM   = re.compile(r"\b(\d{1,2})\s*(?:years?|yrs?)\b", re.I)
_RX_NONE  = re.compile(r"\b(no\s+experience|fresher|fresh\s+grad|entry[-\s]level)\b", re.I)

def extract_years(text: str) -> tuple[Optional[int], Optional[int]]:
    """Return (min_years, max_years). (None, None) if unparseable."""
    if not text:
        return (None, None)
    if _RX_NONE.search(text):
        return (0, 0)
    m = _RX_RANGE.search(text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = _RX_AT_LEAST.search(text)
    if m:
        return (int(m.group(1)), None)
    m = _RX_PLUS.search(text)
    if m:
        return (int(m.group(1)), None)
    m = _RX_NUM.search(text)
    if m:
        n = int(m.group(1))
        return (n, n)
    return (None, None)

# ---------- DOM extraction ----------

JOB_DETAILS_PANEL = (By.CSS_SELECTOR, "div.jobs-details__main-content, div.jobs-search__job-details--container")
JOB_TITLE  = (By.CSS_SELECTOR, "h1.t-24, h1.job-details-jobs-unified-top-card__job-title")
JOB_COMPANY = (By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__company-name a, "
                                ".job-details-jobs-unified-top-card__company-name")
JOB_LOCATION = (By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__primary-description-container span:first-child")
JOB_WORKSTYLE = (By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__workplace-type")
JOB_POSTED   = (By.CSS_SELECTOR, "span.tvm__text--low-emphasis")  # "1 week ago" etc.
JOB_DESCRIPTION = (By.CSS_SELECTOR, "div.jobs-description__container, "
                                   "article.jobs-description__container, "
                                   "div.jobs-box__html-content")
JOB_CARD_ANCHOR = (By.CSS_SELECTOR, "a.job-card-container__link")

def wait_for_details_panel(driver: WebDriver, timeout: int = 15) -> bool:
    return wait_for(driver, *JOB_DETAILS_PANEL, timeout=timeout) is not None

def extract_job_details(driver: WebDriver, job_id: str, jd_url: str) -> dict:
    """Pull title/company/location/work_style/posted/JD/experience from the active panel."""
    if not wait_for_details_panel(driver):
        log.warning("details_panel_missing", extra={"job_id": job_id})
        return {"job_id": job_id, "jd_url": jd_url, "jd_full_text": ""}
    # Click "Show more" if present
    try:
        more = driver.find_element(By.CSS_SELECTOR, "button.jobs-description__footer-button")
        more.click()
        time.sleep(0.5)
    except Exception:
        pass

    title       = text_or_empty(driver, *JOB_TITLE)
    company     = text_or_empty(driver, *JOB_COMPANY)
    location    = text_or_empty(driver, *JOB_LOCATION)
    work_style  = text_or_empty(driver, *JOB_WORKSTYLE)
    posted      = text_or_empty(driver, *JOB_POSTED)
    jd_text     = text_or_empty(driver, *JOB_DESCRIPTION)

    exp_min, exp_max = extract_years(jd_text)

    return {
        "job_id": job_id,
        "title": title or None,
        "company": company or None,
        "location": location or None,
        "work_style": work_style or None,
        "posted_relative": posted or None,
        "experience_text": None,         # not separately surfaced by LI; we use JD-derived
        "experience_min": exp_min,
        "experience_max": exp_max,
        "salary_min_lpa": None,          # parsed in a later iteration if needed
        "salary_max_lpa": None,
        "salary_text": None,
        "jd_full_text": jd_text,
        "jd_url": jd_url,
    }
```

- [ ] **Step 4: Run, confirm years tests pass**

```bash
pytest tests/scraper/test_extract.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/scraper/extract.py tests/scraper/test_extract.py
git commit -m "feat(scraper): JD extraction selectors + years-of-experience regex parser"
```

### Task 5.5: scraper/search.py — apply filters

**Files:**
- Create: `jobscope/scraper/search.py`

Reference: `runAiBot.py::apply_filters`, `set_search_location`. We
simplify — only the filters JobScope uses.

- [ ] **Step 1: Implement search.py**

```python
# jobscope/scraper/search.py
"""Navigate LinkedIn jobs search and apply our filters."""
from __future__ import annotations
import time
from urllib.parse import urlencode, quote
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope import config
from jobscope.scraper._clickers import wait_for, wait_clickable, safe_click
from jobscope.utils.logging import get_logger

log = get_logger("scraper.search")

SEARCH_BASE = "https://www.linkedin.com/jobs/search/"

# LinkedIn URL filter param mapping
_F_EXP = {"Internship":"1","Entry level":"2","Associate":"3",
          "Mid-Senior level":"4","Director":"5","Executive":"6"}
_F_JOB = {"Full-time":"F","Part-time":"P","Contract":"C","Temporary":"T",
          "Internship":"I","Volunteer":"V","Other":"O"}
_F_WP  = {"On-site":"1","Remote":"2","Hybrid":"3"}
_F_DATE = {"Past 24 hours":"r86400","Past week":"r604800","Past month":"r2592000","Any time":""}

def build_search_url(term: str) -> str:
    params = {
        "keywords": term,
        "location": config.SEARCH_LOCATION,
        "f_E": ",".join(_F_EXP[e] for e in config.EXPERIENCE_LEVELS if e in _F_EXP),
        "f_JT": ",".join(_F_JOB[j] for j in config.JOB_TYPES if j in _F_JOB),
        "f_WT": ",".join(_F_WP[w] for w in config.ON_SITE if w in _F_WP),
        "f_TPR": _F_DATE.get(config.DATE_POSTED, ""),
    }
    if config.EASY_APPLY_ONLY:
        params["f_AL"] = "true"
    params = {k: v for k, v in params.items() if v}
    return SEARCH_BASE + "?" + urlencode(params, quote_via=quote)

def navigate_to_search(driver: WebDriver, term: str) -> None:
    url = build_search_url(term)
    log.info("navigate_search", extra={"term": term, "url": url})
    driver.get(url)
    time.sleep(3)
    # Wait for results list
    wait_for(driver, By.CSS_SELECTOR,
             "ul.jobs-search__results-list, div.jobs-search-results-list", timeout=20)
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/scraper/search.py
git commit -m "feat(scraper): build search URL with all configured filters"
```

### Task 5.6: scraper/listing.py — iterate result list + pagination

**Files:**
- Create: `jobscope/scraper/listing.py`

- [ ] **Step 1: Implement listing.py**

```python
# jobscope/scraper/listing.py
"""Iterate job cards in the search-results pane, click each, yield (job_id, url)."""
from __future__ import annotations
import time
from typing import Iterator, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope import config
from jobscope.scraper._clickers import wait_for, safe_click
from jobscope.utils.logging import get_logger

log = get_logger("scraper.listing")

RESULTS_LIST = (By.CSS_SELECTOR, "ul.jobs-search__results-list, div.scaffold-layout__list ul")
JOB_CARD = (By.CSS_SELECTOR, "li[data-occludable-job-id], div.job-card-container")
NEXT_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='View next page']")

def _scroll_into_view(driver: WebDriver, el) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.4)

def iter_listings(driver: WebDriver, max_pages: int = 10) -> Iterator[Tuple[str, str, int, int]]:
    """Yield (job_id, jd_url, page, position_on_page) for each card.
    Clicks each card so the right-hand panel updates for extract.py to read.
    """
    page = 1
    while page <= max_pages:
        results = wait_for(driver, *RESULTS_LIST, timeout=15)
        if not results:
            log.warning("results_list_missing")
            return
        cards = driver.find_elements(*JOB_CARD)
        if not cards:
            log.info("no_cards_on_page", extra={"page": page})
            return
        for idx, card in enumerate(cards, start=1):
            try:
                job_id = card.get_attribute("data-occludable-job-id") \
                         or card.get_attribute("data-job-id") \
                         or ""
                if not job_id:
                    anchor = card.find_element(By.CSS_SELECTOR, "a")
                    href = anchor.get_attribute("href") or ""
                    # /jobs/view/123456789/
                    parts = [p for p in href.split("/") if p.isdigit()]
                    job_id = parts[0] if parts else ""
                jd_url = f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else ""
                _scroll_into_view(driver, card)
                if not safe_click(driver, card):
                    log.warning("card_click_failed", extra={"job_id": job_id})
                    continue
                time.sleep(config.CLICK_GAP_SEC)
                if job_id:
                    yield (job_id, jd_url, page, idx)
            except Exception as e:
                log.warning("listing_iter_error", extra={"err": str(e), "page": page, "idx": idx})
                continue
        # Next page
        try:
            nxt = driver.find_element(*NEXT_PAGE_BTN)
            if nxt.is_enabled():
                safe_click(driver, nxt)
                time.sleep(3)
                page += 1
                continue
        except Exception:
            pass
        return
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/scraper/listing.py
git commit -m "feat(scraper): iterate result-list cards with pagination"
```

### Task 5.7: scraper/applied_detector.py — auto-detect Applied badge

**Files:**
- Create: `jobscope/scraper/applied_detector.py`

- [ ] **Step 1: Implement applied_detector.py**

```python
# jobscope/scraper/applied_detector.py
"""Check whether the currently selected job shows the 'Applied' badge."""
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

APPLIED_SELECTORS = [
    "span.jobs-s-apply__application-aware-text",         # "Applied X ago"
    ".artdeco-inline-feedback--success",                 # success banner
    "button.jobs-apply-button[aria-label*='Applied']",
]

def is_applied(driver: WebDriver) -> bool:
    for sel in APPLIED_SELECTORS:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                txt = (el.text or el.get_attribute("aria-label") or "").lower()
                if "applied" in txt:
                    return True
        except Exception:
            continue
    return False
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/scraper/applied_detector.py
git commit -m "feat(scraper): detect LinkedIn 'Applied' badge from DOM"
```

---

## Phase 6 — State snapshot + decision popup

### Task 6.1: state/snapshot.py — atomic JSON read/write

**Files:**
- Create: `jobscope/state/snapshot.py`
- Test: `tests/state/test_snapshot.py`

- [ ] **Step 1: Write failing test**

```python
# tests/state/test_snapshot.py
from pathlib import Path
from jobscope.state.snapshot import write_snapshot, read_snapshot, idle_payload

def test_write_then_read(tmp_path):
    p = tmp_path / "cur.json"
    write_snapshot(p, {"state": "analyzing", "job_id": "x"})
    out = read_snapshot(p)
    assert out["state"] == "analyzing"
    assert out["job_id"] == "x"
    assert "last_updated_at" in out

def test_read_missing_returns_idle(tmp_path):
    p = tmp_path / "missing.json"
    out = read_snapshot(p)
    assert out["state"] == "idle"

def test_atomic_no_partial(tmp_path):
    p = tmp_path / "cur.json"
    write_snapshot(p, idle_payload(session_id="s"))
    # .tmp should not remain
    assert not (tmp_path / "cur.json.tmp").exists()

def test_idle_payload_contains_required_keys():
    p = idle_payload(session_id="s1")
    assert p["state"] == "idle"
    assert p["session_id"] == "s1"
```

- [ ] **Step 2: Run, confirm failure**

```bash
pytest tests/state/test_snapshot.py -v
```

- [ ] **Step 3: Implement snapshot.py**

```python
# jobscope/state/snapshot.py
"""Atomic JSON snapshot. Writers do .tmp + os.replace; readers tolerate absence."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def idle_payload(session_id: str = "") -> dict[str, Any]:
    return {
        "state": "idle",
        "session_id": session_id,
        "last_updated_at": _now_iso(),
        "scraper_pid": os.getpid(),
    }

def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload.setdefault("last_updated_at", _now_iso())
    payload.setdefault("scraper_pid", os.getpid())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    os.replace(tmp, path)

def read_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"state": "idle", "last_updated_at": _now_iso(), "missing": True}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"state": "error", "error": "snapshot_unparseable",
                "last_updated_at": _now_iso()}
```

- [ ] **Step 4: Run, confirm pass**

```bash
pytest tests/state/test_snapshot.py -v
```

- [ ] **Step 5: Commit**

```bash
git add jobscope/state/snapshot.py tests/state/test_snapshot.py
git commit -m "feat(state): atomic JSON snapshot read/write helpers"
```

### Task 6.2: decision/popup.py — tkinter modal

**Files:**
- Create: `jobscope/decision/popup.py`

(Tkinter is GUI; no unit test. Smoke test via CLI in Task 7.)

- [ ] **Step 1: Implement popup.py**

```python
# jobscope/decision/popup.py
"""Tkinter modal that blocks until user picks Apply / Skip / Bookmark / Quit."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional

DECISIONS = ("apply", "skip", "bookmark", "quit")

def ask_decision(*, title: str, company: str, fit_score: int,
                 recommendation: str) -> Optional[str]:
    """Show a modal and return one of DECISIONS, or None if window closed."""
    result: dict[str, Optional[str]] = {"value": None}

    root = tk.Tk()
    root.title("JobScope — decide")
    root.geometry("520x340")
    root.attributes("-topmost", True)

    pad = {"padx": 16, "pady": 8}

    header = ttk.Label(root, text=f"{title}\n@ {company}",
                       font=("Segoe UI", 12, "bold"), justify="left")
    header.pack(anchor="w", **pad)

    fit_color = "#2ecc71" if fit_score >= 60 else ("#f1c40f" if fit_score >= 40 else "#e74c3c")
    fit = ttk.Label(root, text=f"Fit: {fit_score} / 100", font=("Segoe UI", 14, "bold"))
    fit.pack(anchor="w", padx=16)
    fit.configure(foreground=fit_color)

    rec = tk.Text(root, height=6, wrap="word", font=("Segoe UI", 10))
    rec.insert("1.0", recommendation or "")
    rec.configure(state="disabled")
    rec.pack(fill="both", expand=False, padx=16, pady=8)

    def choose(value: str):
        result["value"] = value
        root.destroy()

    btns = ttk.Frame(root)
    btns.pack(pady=10)
    ttk.Button(btns, text="Apply (A)",     command=lambda: choose("apply")).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Skip (S)",      command=lambda: choose("skip")).grid(row=0, column=1, padx=6)
    ttk.Button(btns, text="Bookmark (B)",  command=lambda: choose("bookmark")).grid(row=0, column=2, padx=6)
    ttk.Button(btns, text="Quit (Q)",      command=lambda: choose("quit")).grid(row=0, column=3, padx=6)

    root.bind("<a>", lambda e: choose("apply"))
    root.bind("<s>", lambda e: choose("skip"))
    root.bind("<b>", lambda e: choose("bookmark"))
    root.bind("<q>", lambda e: choose("quit"))
    root.bind("<Escape>", lambda e: choose("skip"))

    root.mainloop()
    return result["value"]
```

- [ ] **Step 2: Smoke test manually**

Run: `python -c "from jobscope.decision.popup import ask_decision; print(ask_decision(title='Sr AWS Eng', company='Acme', fit_score=67, recommendation='Decent fit. Lambda + API Gateway map well.'))"`
Expected: popup appears; click Apply → prints "apply".

- [ ] **Step 3: Commit**

```bash
git add jobscope/decision/popup.py
git commit -m "feat(decision): tkinter modal popup for Apply/Skip/Bookmark/Quit"
```

---

---

## Phase 7 — Orchestrator + CLI

### Task 7.1: orchestrator.py — the main loop

**Files:**
- Create: `jobscope/orchestrator.py`

This is the only module that imports across boundaries. Each method does one
thing, so the loop reads top-to-bottom.

- [ ] **Step 1: Implement orchestrator.py**

```python
# jobscope/orchestrator.py
"""Main loop: search → for each listing → extract → analyze → snapshot → popup → record → next."""
from __future__ import annotations
import json
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional
import duckdb
from jobscope import config
from jobscope.ai.analyzer import analyze
from jobscope.ai.client import GeminiClient, AnalysisFailure
from jobscope.db import repo
from jobscope.db.connection import open_rw, init_schema
from jobscope.decision.popup import ask_decision
from jobscope.profile.normalize import load_profile, sync_profile_to_db
from jobscope.scraper.applied_detector import is_applied
from jobscope.scraper.browser import new_driver, quit_driver
from jobscope.scraper.extract import extract_job_details
from jobscope.scraper.listing import iter_listings
from jobscope.scraper.login import login, LoginFailure
from jobscope.scraper.search import navigate_to_search
from jobscope.state.snapshot import write_snapshot, idle_payload
from jobscope.utils.logging import get_logger, configure_logging

log = get_logger("orchestrator")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def _snapshot_loading(session_id: str, search_term: str, page: int, pos: int) -> dict:
    return {"state": "loading", "session_id": session_id,
            "search_term": search_term, "page": page, "position_on_page": pos,
            "last_updated_at": _now_iso()}

def _snapshot_analyzing(base: dict, job: dict) -> dict:
    out = dict(base)
    out.update({"state": "analyzing", "job_id": job["job_id"],
                "title": job.get("title"), "company": job.get("company"),
                "last_updated_at": _now_iso()})
    return out

def _snapshot_analyzed(base: dict, job: dict, parsed_dict: dict, stats: dict) -> dict:
    out = dict(base)
    out.update({"state": "analyzed", "job_id": job["job_id"],
                "title": job.get("title"), "company": job.get("company"),
                "analysis": parsed_dict, "stats": stats,
                "last_updated_at": _now_iso()})
    return out

def _snapshot_error(base: dict, job_id: str, kind: str, message: str) -> dict:
    out = dict(base)
    out.update({"state": "error", "job_id": job_id,
                "error": {"kind": kind, "message": message},
                "last_updated_at": _now_iso()})
    return out

def _snapshot_decided(base: dict, job_id: str, decision: str) -> dict:
    out = dict(base)
    out.update({"state": "decided", "job_id": job_id,
                "last_decision": decision, "last_updated_at": _now_iso()})
    return out

def _snapshot_stopped(session_id: str, summary: dict) -> dict:
    return {"state": "stopped", "session_id": session_id,
            "session_summary": summary, "last_updated_at": _now_iso()}

def _gather_stats(conn: duckdb.DuckDBPyConnection) -> dict:
    row = conn.execute(
        "SELECT jobs_evaluated, applied, skipped, bookmarked, avg_fit "
        "FROM v_current_session_stats"
    ).fetchone()
    if not row:
        return {"evaluated": 0, "applied": 0, "skipped": 0, "bookmarked": 0, "avg_fit": None}
    return {"evaluated": row[0] or 0, "applied": row[1] or 0,
            "skipped": row[2] or 0, "bookmarked": row[3] or 0,
            "avg_fit": float(row[4]) if row[4] is not None else None}

def _archive_stale_snapshot() -> None:
    if not config.SNAPSHOT_PATH.exists():
        return
    config.CRASHED_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    target = config.CRASHED_DIR / f"snapshot-{ts}.json"
    config.SNAPSHOT_PATH.replace(target)
    log.info("archived_stale_snapshot", extra={"target": str(target)})

def run() -> int:
    config.ensure_dirs()
    configure_logging(config.LOG_PATH)
    log.info("bot_start")

    # Archive any leftover snapshot from a prior crashed run
    _archive_stale_snapshot()

    # DB + profile
    conn = open_rw(config.DB_PATH)
    init_schema(conn)
    repo.seed_skills_canonical(conn)
    profile = load_profile(config.PROFILE_PATH)
    sync_profile_to_db(conn, profile)

    # Session
    sid = repo.start_session(conn, config.SEARCH_TERMS, config.SEARCH_LOCATION)
    write_snapshot(config.SNAPSHOT_PATH, idle_payload(session_id=sid))

    # Gemini client + canonical skill names (passed into every prompt)
    canon = [r[0] for r in conn.execute("SELECT skill_canonical FROM skills_canonical").fetchall()]
    gem = GeminiClient(keys=config.GEMINI_API_KEYS, model=config.GEMINI_MODEL)

    # Selenium
    driver = new_driver()
    try:
        login(driver, on_verification=lambda: _wait_for_user_verify())
    except LoginFailure as e:
        log.error("login_failed", extra={"err": str(e)})
        write_snapshot(config.SNAPSHOT_PATH,
                       _snapshot_error({"session_id": sid}, "", "login", str(e)))
        quit_driver(driver); conn.close()
        return 2

    quit_requested = False
    def _on_sigint(*_):
        nonlocal quit_requested
        quit_requested = True
        log.warning("sigint_received")
    signal.signal(signal.SIGINT, _on_sigint)

    try:
        for term in config.SEARCH_TERMS:
            if quit_requested: break
            navigate_to_search(driver, term)
            for n, (job_id, jd_url, page, pos) in enumerate(iter_listings(driver), start=1):
                if quit_requested: break
                base = _snapshot_loading(sid, term, page, pos)
                write_snapshot(config.SNAPSHOT_PATH, base)

                job = extract_job_details(driver, job_id=job_id, jd_url=jd_url)
                job.update({"session_id": sid,
                            "scraped_at": datetime.now(timezone.utc),
                            "search_term": term})
                repo.upsert_job(conn, job)
                repo.touch_current_job(conn, job_id)

                if not job.get("jd_full_text"):
                    repo.mark_job_status(conn, job_id, "failed", "jd_empty")
                    write_snapshot(config.SNAPSHOT_PATH,
                                   _snapshot_error(base, job_id, "jd_empty", "no JD text"))
                    continue

                write_snapshot(config.SNAPSHOT_PATH, _snapshot_analyzing(base, job))
                try:
                    parsed, raw, latency = analyze(gem, profile=profile,
                                                   skills_canonical=canon, job=job)
                except AnalysisFailure as e:
                    repo.mark_job_status(conn, job_id, "failed", str(e))
                    write_snapshot(config.SNAPSHOT_PATH,
                                   _snapshot_error(base, job_id, "analysis", str(e)))
                    continue

                repo.insert_analysis(conn, job_id=job_id,
                                     prompt_version=config.PROMPT_VERSION,
                                     model_name=config.GEMINI_MODEL,
                                     latency_ms=latency,
                                     parsed=parsed.model_dump(),
                                     raw_json=raw)
                repo.replace_job_skills(conn, job_id,
                    [{"canonical": s.canonical, "as_written": s.as_written, "kind": s.kind}
                     for s in parsed.skills])
                repo.mark_job_status(conn, job_id, "analyzed")

                stats = _gather_stats(conn)
                write_snapshot(config.SNAPSHOT_PATH,
                               _snapshot_analyzed(base, job, parsed.model_dump(), stats))

                # Decision popup
                decision = ask_decision(
                    title=job.get("title") or "Untitled",
                    company=job.get("company") or "Unknown",
                    fit_score=parsed.fit_score,
                    recommendation=parsed.recommendation,
                )
                if decision is None or decision == "quit":
                    quit_requested = True
                    break

                repo.record_decision(conn, job_id=job_id, session_id=sid,
                                     decision=decision, source="user")
                # Auto-detect Applied badge as additional signal
                if decision != "apply" and is_applied(driver):
                    repo.record_decision(conn, job_id=job_id, session_id=sid,
                                         decision="apply", source="auto_detected_applied")

                write_snapshot(config.SNAPSHOT_PATH,
                               _snapshot_decided(base, job_id, decision))

                if n % config.SWITCH_AFTER == 0:
                    log.info("switch_term", extra={"after_n": n})
                    break

        repo.end_session(conn, sid, "user_quit" if quit_requested else "completed")
        write_snapshot(config.SNAPSHOT_PATH, _snapshot_stopped(sid, _gather_stats(conn)))
        return 0
    except Exception as e:
        log.exception("orchestrator_crash")
        repo.end_session(conn, sid, "crashed")
        write_snapshot(config.SNAPSHOT_PATH,
                       _snapshot_error({"session_id": sid}, "", "crash", str(e)))
        return 1
    finally:
        quit_driver(driver)
        conn.close()

def _wait_for_user_verify() -> None:
    """Tk popup that blocks while the user solves a captcha/2FA in the browser."""
    import tkinter as tk
    root = tk.Tk(); root.title("JobScope — verification required")
    root.geometry("420x140"); root.attributes("-topmost", True)
    tk.Label(root, text="LinkedIn shows a verification step.\n"
                        "Solve it in the browser, then click OK.",
             font=("Segoe UI", 10), justify="left").pack(padx=16, pady=16)
    tk.Button(root, text="OK", width=12, command=root.destroy).pack(pady=8)
    root.mainloop()
```

- [ ] **Step 2: Commit**

```bash
git add jobscope/orchestrator.py
git commit -m "feat(orchestrator): main loop wiring scraper + AI + DB + snapshot + popup"
```

### Task 7.2: cli.py — click commands

**Files:**
- Create: `jobscope/cli.py`
- Create: `jobscope/__main__.py`

- [ ] **Step 1: Write __main__.py**

```python
# jobscope/__main__.py
from jobscope.cli import main
if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write cli.py**

```python
# jobscope/cli.py
"""CLI entry points."""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
import click
from jobscope import config
from jobscope.db.connection import open_rw, init_schema
from jobscope.db import repo
from jobscope.profile.normalize import load_profile, sync_profile_to_db
from jobscope.state.snapshot import write_snapshot, idle_payload
from jobscope.utils.logging import configure_logging, get_logger

log = get_logger("cli")

@click.group()
def main():
    """JobScope command line."""
    config.ensure_dirs()
    configure_logging(config.LOG_PATH)

@main.command()
def run():
    """Start the bot: log in, iterate jobs, analyze, prompt for decisions."""
    from jobscope.orchestrator import run as run_bot
    sys.exit(run_bot())

@main.command("seed-skills")
def seed_skills():
    """Load (or refresh) skills_canonical from seed_skills.csv."""
    conn = open_rw(config.DB_PATH); init_schema(conn)
    n = repo.seed_skills_canonical(conn)
    click.echo(f"Loaded {n} canonical skills.")
    conn.close()

@main.command("parse-resume")
def parse_resume():
    """Verify resume PDF parses (sanity); load profile.json into DB."""
    from jobscope.profile.parse_resume import extract_text
    text = extract_text(config.RESUME_PDF)
    click.echo(f"Resume parsed: {len(text)} chars.")
    conn = open_rw(config.DB_PATH); init_schema(conn)
    p = load_profile(config.PROFILE_PATH)
    sync_profile_to_db(conn, p)
    click.echo(f"Synced profile + {len(p['skills'])} user skills to DB.")
    conn.close()

@main.command("clear-live")
def clear_live():
    """Reset current_job.json to idle."""
    write_snapshot(config.SNAPSHOT_PATH, idle_payload())
    click.echo(f"Cleared {config.SNAPSHOT_PATH}")

@main.command()
@click.option("--confirm", is_flag=True, required=True,
              help="Required to confirm destructive wipe")
def reset(confirm: bool):
    """Archive the DB and recreate empty tables."""
    if config.DB_PATH.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        bak = config.DB_PATH.with_name(f"{config.DB_PATH.name}.bak-{ts}")
        config.DB_PATH.replace(bak)
        click.echo(f"Archived {config.DB_PATH} → {bak.name}")
    if config.SNAPSHOT_PATH.exists():
        config.SNAPSHOT_PATH.unlink()
    conn = open_rw(config.DB_PATH); init_schema(conn)
    repo.seed_skills_canonical(conn)
    conn.close()
    click.echo("Fresh DB created with seeded skills.")

@main.command("login-only")
def login_only():
    """Open Chrome and log in; useful to clear captcha walls before a run."""
    from jobscope.scraper.browser import new_driver, quit_driver
    from jobscope.scraper.login import login
    d = new_driver()
    try:
        login(d, on_verification=lambda: input("Solve verification, then press Enter..."))
        click.echo("Logged in. Closing browser.")
    finally:
        quit_driver(d)
```

- [ ] **Step 3: Smoke test CLI discovery**

```bash
python -m jobscope --help
```
Expected: lists `run / seed-skills / parse-resume / clear-live / reset / login-only`.

- [ ] **Step 4: Smoke test seed-skills**

```bash
python -m jobscope seed-skills
```
Expected: "Loaded 80 canonical skills." (or close to it).

- [ ] **Step 5: Smoke test parse-resume**

```bash
python -m jobscope parse-resume
```
Expected: "Resume parsed: <N> chars. Synced profile + 26 user skills to DB."

- [ ] **Step 6: Commit**

```bash
git add jobscope/cli.py jobscope/__main__.py
git commit -m "feat(cli): click commands for run/reset/clear-live/seed-skills/parse-resume/login-only"
```

---

## Phase 8 — Jetro canvas: frames + refresh scripts

The canvas is split into two: `live` (cockpit) and `historical` (dashboard).
The implementing agent must use the `jet_canvas` and `jet_render` MCP tools
(available in this Jetro workspace) to create canvases and render frames.

### Task 8.1: project.json + canvas creation

**Files:**
- Create: `projects/jobscope/project.json`

- [ ] **Step 1: Write project.json**

```json
{
  "name": "JobScope",
  "slug": "jobscope",
  "description": "Personal LinkedIn job-market intelligence",
  "mode": "research",
  "linkedConnectors": [],
  "linkedTemplates": [],
  "linkedRecipes": []
}
```

- [ ] **Step 2: Create the two canvases via Jetro**

Use the MCP tool from inside Claude Code:
- Call `jet_canvas` to list current canvases under projectSlug `jobscope`.
- Create a canvas titled `Live Cockpit` (project-scoped to `jobscope`).
- Create a canvas titled `Historical Dashboard` (project-scoped to `jobscope`).
- Enable C2 mode on `Live Cockpit` only (`jet_canvas({ action:'enableC2', canvasId: <live_id> })`).

Record both canvas IDs in `PROGRESS.md` under a new "Canvas IDs" section.

- [ ] **Step 3: Commit project.json**

```bash
git add projects/jobscope/project.json
git commit -m "chore(project): jobscope Jetro project manifest"
```

### Task 8.2: .jetro/scripts/refresh_current_job.py — live hub

**Files:**
- Create: `.jetro/scripts/refresh_current_job.py`

Refresh-binding scripts run on a timer, print JSON to stdout, and the JSON is
posted to the bound frame via `jet:refresh`. We bind ONE script to the hub
frame; it broadcasts to the other live frames via `__JET.send` (set up in 8.3).

- [ ] **Step 1: Write refresh_current_job.py**

```python
# .jetro/scripts/refresh_current_job.py
"""Read current_job.json; emit a uniform payload for the live cockpit hub."""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("JET_WORKSPACE", ".")).resolve()
SNAPSHOT = WORKSPACE / "projects" / "jobscope" / "state" / "current_job.json"

def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def _staleness(updated_at_iso: str) -> str:
    try:
        u = datetime.fromisoformat(updated_at_iso.replace("Z", "+00:00"))
        secs = (datetime.now(timezone.utc) - u).total_seconds()
    except Exception:
        return "unknown"
    if secs < 10:   return "live"
    if secs < 60:   return "slow"
    return "stalled"

def main() -> None:
    if not SNAPSHOT.exists():
        payload = {"state": "missing", "_meta": {"computed_at": _iso()}}
    else:
        try:
            payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        except Exception as e:
            payload = {"state": "error", "error": {"kind": "snapshot_parse", "message": str(e)}}
    payload["_meta"] = {
        "computed_at": _iso(),
        "staleness": _staleness(payload.get("last_updated_at", "")),
    }
    sys.stdout.write(json.dumps(payload, default=str))

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test manually**

Run: `python .jetro/scripts/refresh_current_job.py`
Expected: prints a JSON object with `state` and `_meta.staleness`.

- [ ] **Step 3: Commit**

```bash
git add .jetro/scripts/refresh_current_job.py
git commit -m "feat(canvas): refresh script for live cockpit hub"
```

### Task 8.3: Live cockpit hub frame + C2 broadcasting

**Files:**
- Create: `.jetro/frames/live_hub.html` (invisible-ish hub that broadcasts on `current_job`)

- [ ] **Step 1: Write hub HTML**

```html
<!-- .jetro/frames/live_hub.html -->
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>JobScope Live Hub</title>
<style>
  body { margin:0; font-family: ui-sans-serif, system-ui; background:#0e1116; color:#e6edf3; padding:12px; }
  .row { display:flex; justify-content:space-between; gap:12px; align-items:center; }
  .pill { padding:4px 10px; border-radius:999px; font-size:12px; font-weight:600; }
  .live{background:#1f6f3a;color:#d6ffd6}.slow{background:#7a6a1a;color:#fff3a8}
  .stalled{background:#7a1a1a;color:#ffd6d6}.missing{background:#3a3f47;color:#aab2bb}
  .small { font-size:12px; color:#9aa4ad; }
</style></head>
<body>
  <div class="row">
    <div>
      <div id="state" class="pill missing">missing</div>
      <span id="sess" class="small"></span>
    </div>
    <div class="small">updated <span id="upd">—</span></div>
  </div>
  <script>
    __JET.declarePorts && __JET.declarePorts({ outputs: ["current_job"] });
    function render(d){
      const pill = document.getElementById('state');
      pill.textContent = d.state || 'unknown';
      pill.className = 'pill ' + ((d._meta && d._meta.staleness) || 'missing');
      document.getElementById('sess').textContent = d.session_id || '';
      document.getElementById('upd').textContent = (d._meta && d._meta.computed_at) || '';
      __JET.send('current_job', d);
    }
    window.addEventListener('jet:refresh', e => render(e.detail || {}));
  </script>
</body></html>
```

- [ ] **Step 2: Render and bind via Jetro**

From Claude Code, using the Jetro MCP tools:
1. `jet_render({ type:'frame', data:{ title:'Live Hub', file:'.jetro/frames/live_hub.html' }, projectSlug:'jobscope', canvasId: <live_id> })`. Capture the element id.
2. `jet_canvas({ action:'bind', canvasId: <live_id>, elementId: <hub_id>, refreshBinding: { scriptPath:'.jetro/scripts/refresh_current_job.py', intervalMs: 2000 } })`.

- [ ] **Step 3: Commit**

```bash
git add .jetro/frames/live_hub.html
git commit -m "feat(canvas): live hub frame broadcasts current_job on C2 wire"
```

### Task 8.4: Live cockpit subscriber frames (8 frames)

**Files:**
- Create: `.jetro/frames/live_header.html`
- Create: `.jetro/frames/live_fit_gauge.html`
- Create: `.jetro/frames/live_skills.html`
- Create: `.jetro/frames/live_experience.html`
- Create: `.jetro/frames/live_red_flags.html`
- Create: `.jetro/frames/live_recommendation.html`
- Create: `.jetro/frames/live_resume_tailoring.html`
- Create: `.jetro/frames/live_bot_status.html`

All subscribers use `__JET.on('current_job', cb)`. Bind ZERO refresh scripts —
they're pure consumers. The hub feeds them.

- [ ] **Step 1: Write live_header.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Job</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:14px}
  h1{margin:0 0 4px;font-size:20px}
  .sub{color:#9aa4ad;font-size:13px}
</style></head>
<body>
<h1 id="t">—</h1>
<div class="sub"><span id="c">—</span> · <span id="l">—</span> · <span id="w">—</span></div>
<script>
  function show(d){
    document.getElementById('t').textContent = d.title || '(no job)';
    document.getElementById('c').textContent = d.company || '—';
    document.getElementById('l').textContent = (d.analysis && d.analysis.experience_verdict) ? '' : '';
    document.getElementById('l').textContent = d.location || (d.search_term ? 'searching '+d.search_term : '—');
    document.getElementById('w').textContent = d.work_style || '';
  }
  __JET.on('current_job', show);
</script></body></html>
```

- [ ] **Step 2: Write live_fit_gauge.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Fit</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:14px;text-align:center}
  .num{font-size:60px;font-weight:700;line-height:1}
  .label{font-size:12px;color:#9aa4ad;margin-top:6px;letter-spacing:.1em;text-transform:uppercase}
</style></head>
<body>
<div class="num" id="n">—</div>
<div class="label">Fit score</div>
<script>
  function color(s){ if(s>=80)return'#2ecc71'; if(s>=60)return'#a5d610'; if(s>=40)return'#f1c40f'; if(s>=20)return'#e67e22'; return'#e74c3c'; }
  __JET.on('current_job', d => {
    const a = d.analysis || {};
    const s = (typeof a.fit_score === 'number') ? a.fit_score : null;
    const n = document.getElementById('n');
    if (s == null) { n.textContent='—'; n.style.color='#9aa4ad'; }
    else { n.textContent = s; n.style.color = color(s); }
  });
</script></body></html>
```

- [ ] **Step 3: Write live_skills.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Skills</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:12px}
  .cols{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
  .col h3{margin:0 0 6px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#9aa4ad}
  .chip{display:inline-block;padding:4px 8px;margin:2px;border-radius:6px;font-size:12px}
  .ok{background:#15321f;color:#9dffb0}.miss{background:#3a1418;color:#ffb0b6}.nice{background:#2a2a3a;color:#cad1ff}
</style></head>
<body>
<div class="cols">
  <div class="col"><h3>Matched</h3><div id="m">—</div></div>
  <div class="col"><h3>Missing required</h3><div id="x">—</div></div>
  <div class="col"><h3>Nice-to-have</h3><div id="n">—</div></div>
</div>
<script>
  // We don't have user_skills client-side; the hub payload doesn't include them.
  // Approximation: "required" → missing; "nice_to_have" → nice. Matched is empty by default.
  // (Historical dashboard does the proper matched/missing computation via SQL.)
  __JET.on('current_job', d => {
    const skills = (d.analysis && d.analysis.skills) || [];
    const m = document.getElementById('m'); m.innerHTML = '<span class="chip ok">—</span>';
    const x = document.getElementById('x'); x.innerHTML = '';
    const n = document.getElementById('n'); n.innerHTML = '';
    for (const s of skills){
      const txt = s.as_written || s.canonical;
      if (s.kind === 'required')  x.insertAdjacentHTML('beforeend', '<span class="chip miss">'+txt+'</span>');
      else                        n.insertAdjacentHTML('beforeend', '<span class="chip nice">'+txt+'</span>');
    }
  });
</script></body></html>
```

- [ ] **Step 4: Write live_experience.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Experience</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:14px}
  .row{display:flex;gap:14px;align-items:baseline}
  .num{font-size:28px;font-weight:700}
  .v{padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600}
  .in_range{background:#15321f;color:#9dffb0}
  .under{background:#3a3214;color:#ffe7a8}
  .over{background:#3a1428;color:#ffb0d6}
  .way_over{background:#3a1418;color:#ffb0b6}
</style></head>
<body>
<div class="row"><div class="num" id="r">—</div><div class="v" id="v">—</div></div>
<div style="color:#9aa4ad;font-size:12px;margin-top:6px">You: <span id="me">—</span> yrs</div>
<script>
  __JET.on('current_job', d => {
    const a = d.analysis || {};
    const lo = a.experience_min_years, hi = a.experience_max_years;
    document.getElementById('r').textContent =
      (lo == null && hi == null) ? '—' :
      (hi == null) ? (lo + '+ yrs') :
      (lo === hi)  ? (lo + ' yrs') :
      (lo + '–' + hi + ' yrs');
    const v = document.getElementById('v');
    v.textContent = a.experience_verdict || '—';
    v.className = 'v ' + (a.experience_verdict || '');
    document.getElementById('me').textContent = '2';
  });
</script></body></html>
```

- [ ] **Step 5: Write live_red_flags.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Red flags</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:12px}
  .chip{display:inline-block;padding:4px 8px;margin:2px;border-radius:6px;font-size:12px;background:#3a1418;color:#ffb0b6}
  .none{color:#9aa4ad;font-size:12px}
</style></head>
<body>
<div id="f"><span class="none">—</span></div>
<script>
  __JET.on('current_job', d => {
    const f = (d.analysis && d.analysis.red_flags) || [];
    const out = document.getElementById('f');
    if (!f.length){ out.innerHTML = '<span class="none">No red flags</span>'; return; }
    out.innerHTML = f.map(r => '<span class="chip" title="'+(r.text||'')+'">'+r.kind+'</span>').join('');
  });
</script></body></html>
```

- [ ] **Step 6: Write live_recommendation.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Recommendation</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:14px;line-height:1.45}
  h3{margin:0 0 8px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#9aa4ad}
</style></head>
<body><h3>AI recommendation</h3><div id="r" style="font-size:14px">—</div>
<script>
  __JET.on('current_job', d => {
    document.getElementById('r').textContent = (d.analysis && d.analysis.recommendation) || '—';
  });
</script></body></html>
```

- [ ] **Step 7: Write live_resume_tailoring.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Resume tailoring</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:14px;line-height:1.45}
  h3{margin:0 0 8px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#9aa4ad}
</style></head>
<body><h3>Resume tailoring</h3><div id="t" style="font-size:14px">—</div>
<script>
  __JET.on('current_job', d => {
    document.getElementById('t').textContent = (d.analysis && d.analysis.resume_tailoring) || '—';
  });
</script></body></html>
```

- [ ] **Step 8: Write live_bot_status.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Bot status</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:14px}
  .row{display:flex;justify-content:space-between;align-items:center}
  .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}
  .live{background:#2ecc71}.slow{background:#f1c40f}.stalled{background:#e74c3c}.missing{background:#7f8a94}
  .small{color:#9aa4ad;font-size:12px}
</style></head>
<body>
<div class="row">
  <div><span id="dot" class="dot missing"></span><span id="state">missing</span></div>
  <div class="small"><span id="upd">—</span></div>
</div>
<div class="small" style="margin-top:6px">Session: <span id="sid">—</span></div>
<script>
  __JET.on('current_job', d => {
    const s = (d._meta && d._meta.staleness) || 'missing';
    const dot = document.getElementById('dot'); dot.className = 'dot ' + s;
    document.getElementById('state').textContent = d.state || 'unknown';
    document.getElementById('upd').textContent = (d._meta && d._meta.computed_at) || '—';
    document.getElementById('sid').textContent = d.session_id || '—';
  });
</script></body></html>
```

- [ ] **Step 9: Render and wire all 8 frames**

For each frame, use `jet_render` (target the `Live Cockpit` canvas, projectSlug `jobscope`) and capture element id. Then create C2 wires from the hub:

For each subscriber id:
`jet_canvas({ action:'addWire', canvasId: <live_id>, sourceId: <hub_id>, targetId: <subscriber_id>, channel:'current_job' })`

Record element IDs in `PROGRESS.md`.

- [ ] **Step 10: Commit**

```bash
git add .jetro/frames/live_*.html
git commit -m "feat(canvas): 8 subscriber frames listening on current_job wire"
```

### Task 8.5: Live session KPI bar (DB-driven)

**Files:**
- Create: `.jetro/scripts/refresh_session_kpis.py`
- Create: `.jetro/frames/live_session_kpis.html`

- [ ] **Step 1: Write refresh script**

```python
# .jetro/scripts/refresh_session_kpis.py
"""Query v_current_session_stats; emit a small KPI payload."""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
import duckdb

WS = Path(os.environ.get("JET_WORKSPACE", ".")).resolve()
DB = WS / "projects" / "jobscope" / "jobscope.duckdb"

def main():
    out = {"_meta": {"computed_at": datetime.now(timezone.utc).isoformat()}}
    if not DB.exists():
        out.update({"evaluated":0,"applied":0,"skipped":0,"bookmarked":0,"avg_fit":None})
        sys.stdout.write(json.dumps(out)); return
    c = duckdb.connect(str(DB), read_only=True)
    try:
        row = c.execute("SELECT jobs_evaluated, applied, skipped, bookmarked, avg_fit "
                        "FROM v_current_session_stats").fetchone()
        if row:
            out.update({"evaluated":row[0] or 0, "applied":row[1] or 0,
                        "skipped":row[2] or 0, "bookmarked":row[3] or 0,
                        "avg_fit": float(row[4]) if row[4] is not None else None})
        else:
            out.update({"evaluated":0,"applied":0,"skipped":0,"bookmarked":0,"avg_fit":None})
    finally:
        c.close()
    sys.stdout.write(json.dumps(out))

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write KPI frame**

```html
<!-- .jetro/frames/live_session_kpis.html -->
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Session KPIs</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:14px}
  .row{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
  .k{background:#161b22;border-radius:10px;padding:10px;text-align:center}
  .v{font-size:22px;font-weight:700}
  .l{font-size:11px;color:#9aa4ad;letter-spacing:.08em;text-transform:uppercase;margin-top:4px}
</style></head>
<body>
<div class="row">
  <div class="k"><div class="v" id="e">0</div><div class="l">evaluated</div></div>
  <div class="k"><div class="v" id="a">0</div><div class="l">applied</div></div>
  <div class="k"><div class="v" id="s">0</div><div class="l">skipped</div></div>
  <div class="k"><div class="v" id="b">0</div><div class="l">bookmarked</div></div>
  <div class="k"><div class="v" id="f">—</div><div class="l">avg fit</div></div>
</div>
<script>
  window.addEventListener('jet:refresh', e => {
    const d = e.detail || {};
    document.getElementById('e').textContent = d.evaluated ?? 0;
    document.getElementById('a').textContent = d.applied ?? 0;
    document.getElementById('s').textContent = d.skipped ?? 0;
    document.getElementById('b').textContent = d.bookmarked ?? 0;
    document.getElementById('f').textContent = d.avg_fit == null ? '—' : d.avg_fit.toFixed(1);
  });
</script></body></html>
```

- [ ] **Step 3: Render + bind**

`jet_render` the KPI frame onto Live Cockpit. Then bind:
`jet_canvas({ action:'bind', canvasId:<live_id>, elementId:<kpi_id>, refreshBinding: { scriptPath:'.jetro/scripts/refresh_session_kpis.py', intervalMs: 5000 } })`

- [ ] **Step 4: Commit**

```bash
git add .jetro/scripts/refresh_session_kpis.py .jetro/frames/live_session_kpis.html
git commit -m "feat(canvas): live session KPIs (DB-driven, 5s refresh)"
```

### Task 8.6: Historical refresh scripts + frames (4 charts)

**Files:**
- Create: `.jetro/scripts/refresh_skill_gaps.py`
- Create: `.jetro/scripts/refresh_fit_distribution.py`
- Create: `.jetro/scripts/refresh_salary_map.py`
- Create: `.jetro/scripts/refresh_search_term_report.py`
- Create: `.jetro/frames/hist_skill_gaps.html`
- Create: `.jetro/frames/hist_fit_distribution.html`
- Create: `.jetro/frames/hist_salary_map.html`
- Create: `.jetro/frames/hist_search_term_report.html`

Each refresh script opens the DB read-only and emits a Plotly-ready payload.

- [ ] **Step 1: refresh_skill_gaps.py**

```python
# .jetro/scripts/refresh_skill_gaps.py
import json, os, sys
from pathlib import Path
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"rows":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("""
      SELECT display_name, jobs_asking, jobs_where_missing
      FROM v_skill_gaps
      WHERE jobs_where_missing > 0
      ORDER BY jobs_where_missing DESC LIMIT 25
    """).fetchall()
    c.close()
    sys.stdout.write(json.dumps({"rows":[
        {"skill":r[0],"asking":r[1],"missing":r[2]} for r in rows]}))
if __name__ == "__main__": main()
```

- [ ] **Step 2: hist_skill_gaps.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Skill gaps</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>body{margin:0;background:#0e1116;color:#e6edf3;font-family:ui-sans-serif,system-ui}</style>
</head><body>
<div id="c" style="width:100%;height:100%"></div>
<script>
  function plot(d){
    const rows = (d && d.rows) || [];
    const skills = rows.map(r=>r.skill).reverse();
    const miss   = rows.map(r=>r.missing).reverse();
    Plotly.react('c', [{type:'bar',orientation:'h',x:miss,y:skills,
      marker:{color:'#e74c3c'},hovertemplate:'%{y}: missing in %{x} jobs<extra></extra>'}],
      {paper_bgcolor:'#0e1116',plot_bgcolor:'#0e1116',
       font:{color:'#e6edf3'},margin:{l:140,r:20,t:20,b:30},
       xaxis:{title:'Jobs where missing'},yaxis:{automargin:true}},
      {displayModeBar:false,responsive:true});
  }
  window.addEventListener('jet:refresh', e => plot(e.detail || {}));
</script></body></html>
```

- [ ] **Step 3: refresh_fit_distribution.py**

```python
# .jetro/scripts/refresh_fit_distribution.py
import json, os, sys
from pathlib import Path
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"scores":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("SELECT fit_score FROM v_job_analysis WHERE fit_score IS NOT NULL").fetchall()
    c.close()
    sys.stdout.write(json.dumps({"scores":[r[0] for r in rows]}))
if __name__ == "__main__": main()
```

- [ ] **Step 4: hist_fit_distribution.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Fit distribution</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>body{margin:0;background:#0e1116;color:#e6edf3;font-family:ui-sans-serif,system-ui}</style>
</head><body>
<div id="c" style="width:100%;height:100%"></div>
<script>
  function plot(d){
    const xs = (d && d.scores) || [];
    Plotly.react('c', [{type:'histogram',x:xs,xbins:{start:0,end:100,size:10},
      marker:{color:'#5dade2'}}],
      {paper_bgcolor:'#0e1116',plot_bgcolor:'#0e1116',font:{color:'#e6edf3'},
       margin:{l:40,r:20,t:20,b:40},bargap:0.05,
       xaxis:{title:'Fit score',range:[0,100]},yaxis:{title:'Jobs'}},
      {displayModeBar:false,responsive:true});
  }
  window.addEventListener('jet:refresh', e => plot(e.detail||{}));
</script></body></html>
```

- [ ] **Step 5: refresh_salary_map.py**

```python
# .jetro/scripts/refresh_salary_map.py
import json, os, sys
from pathlib import Path
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"rows":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("""
      SELECT search_term, salary_min_lpa, salary_max_lpa
      FROM jobs
      WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL
    """).fetchall()
    c.close()
    sys.stdout.write(json.dumps({"rows":[
        {"term":r[0],"min":r[1],"max":r[2]} for r in rows]}))
if __name__ == "__main__": main()
```

- [ ] **Step 6: hist_salary_map.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Salary map</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>body{margin:0;background:#0e1116;color:#e6edf3;font-family:ui-sans-serif,system-ui;padding:8px}
.empty{padding:20px;color:#9aa4ad;font-size:13px;text-align:center}</style>
</head><body>
<div id="c" style="width:100%;height:90%"></div>
<div id="empty" class="empty" style="display:none">No salary data found in JDs yet.</div>
<script>
  function plot(d){
    const rows = (d && d.rows) || [];
    const empty = document.getElementById('empty');
    if (!rows.length){ document.getElementById('c').style.display='none'; empty.style.display='block'; return; }
    document.getElementById('c').style.display='block'; empty.style.display='none';
    const terms = [...new Set(rows.map(r=>r.term))];
    const traces = terms.map(t => ({
      type:'box', name:t, orientation:'h',
      x: rows.filter(r=>r.term===t).flatMap(r=>[r.min,r.max].filter(v=>v!=null)),
    }));
    Plotly.react('c', traces, {
      paper_bgcolor:'#0e1116',plot_bgcolor:'#0e1116',font:{color:'#e6edf3'},
      margin:{l:160,r:20,t:20,b:40}, xaxis:{title:'LPA'}, showlegend:false,
      shapes:[{type:'line',x0:12,x1:12,yref:'paper',y0:0,y1:1,
               line:{color:'#f1c40f',dash:'dash'}}],
      annotations:[{x:12,yref:'paper',y:1.02,text:'expected 12 LPA',
                    showarrow:false,font:{color:'#f1c40f',size:11}}]
    }, {displayModeBar:false,responsive:true});
  }
  window.addEventListener('jet:refresh', e => plot(e.detail||{}));
</script></body></html>
```

- [ ] **Step 7: refresh_search_term_report.py**

```python
# .jetro/scripts/refresh_search_term_report.py
import json, os, sys
from pathlib import Path
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"rows":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("""
      SELECT search_term, jobs_seen, avg_fit, applied, skipped, apply_rate_pct
      FROM v_search_term_report
    """).fetchall()
    c.close()
    sys.stdout.write(json.dumps({"rows":[{
        "term":r[0],"seen":r[1],"avg_fit":r[2],"applied":r[3],
        "skipped":r[4],"apply_rate":r[5]
    } for r in rows]}))
if __name__ == "__main__": main()
```

- [ ] **Step 8: hist_search_term_report.html**

```html
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Search term report</title>
<style>
  body{margin:0;font-family:ui-sans-serif,system-ui;background:#0e1116;color:#e6edf3;padding:12px}
  table{border-collapse:collapse;width:100%;font-size:13px}
  th,td{padding:8px 10px;text-align:right;border-bottom:1px solid #21262d}
  th{font-weight:600;color:#9aa4ad;letter-spacing:.05em;text-transform:uppercase;font-size:11px}
  th:first-child,td:first-child{text-align:left}
</style></head><body>
<table>
  <thead><tr><th>Search term</th><th>Seen</th><th>Avg fit</th><th>Applied</th><th>Skipped</th><th>Apply %</th></tr></thead>
  <tbody id="t"><tr><td colspan="6" style="color:#9aa4ad;text-align:center">No data yet</td></tr></tbody>
</table>
<script>
  function render(d){
    const rows = (d && d.rows) || [];
    const tb = document.getElementById('t');
    if (!rows.length){ tb.innerHTML = '<tr><td colspan="6" style="color:#9aa4ad;text-align:center">No data yet</td></tr>'; return; }
    tb.innerHTML = rows.map(r =>
      `<tr><td>${r.term}</td><td>${r.seen ?? 0}</td>`+
      `<td>${r.avg_fit ?? '—'}</td><td>${r.applied ?? 0}</td>`+
      `<td>${r.skipped ?? 0}</td><td>${r.apply_rate ?? '—'}</td></tr>`).join('');
  }
  window.addEventListener('jet:refresh', e => render(e.detail||{}));
</script></body></html>
```

- [ ] **Step 9: Render + bind all 4 historical frames**

For each, `jet_render` onto `Historical Dashboard` (projectSlug `jobscope`), then `jet_canvas action:'bind'` with `intervalMs: 30000`.

- [ ] **Step 10: Commit**

```bash
git add .jetro/scripts/refresh_skill_gaps.py .jetro/scripts/refresh_fit_distribution.py .jetro/scripts/refresh_salary_map.py .jetro/scripts/refresh_search_term_report.py .jetro/frames/hist_*.html
git commit -m "feat(canvas): 4 historical charts with 30s DuckDB refresh"
```

---

## Phase 9 — Jetro skill, deploy, demo prep, README

### Task 9.1: Ship the Jetro skill

**Files:**
- Create: `.jetro/skills/jobscope_dashboard.md`

This skill teaches the Jetro agent how to build extra JobScope dashboards from
the DuckDB schema in natural language. Discoverable via `jet_skill`.

- [ ] **Step 1: Write the skill**

```markdown
---
name: JobScope Dashboard
description: Build job-analysis dashboards from the JobScope DuckDB at projects/jobscope/jobscope.duckdb. Covers schema, canonical views, and idiomatic frame patterns.
---

# JobScope Dashboard Skill

Use this when the user asks for any new chart/table/insight derived from their
JobScope evaluation data. The DB lives at `projects/jobscope/jobscope.duckdb`.

## Tables (canonical)

- `jobs` — one row per LinkedIn job scraped
- `analyses` — one row per Gemini analysis, versioned by `prompt_version`
- `job_skills(job_id, skill_canonical, skill_as_written, kind)` — `kind ∈ {required, nice_to_have}`
- `skills_canonical(skill_canonical, display_name, category, aliases)`
- `user_skills(skill_canonical, proficiency, years)` — the candidate's profile
- `user_profile` — single row with name, experience, ctc
- `decisions(job_id, session_id, decided_at, decision, source)` — event-sourced; `decision ∈ {apply, skip, bookmark}`
- `sessions(session_id, started_at, ended_at, search_terms, ...)`
- `session_state` — single row pointer to current session/job

## Views you should prefer over base tables

- `v_job_analysis` — jobs JOIN latest analysis + latest decision (use this for per-job rendering)
- `v_skill_gaps` — required skills NOT in user_skills, ranked by frequency
- `v_search_term_report` — per-search-term jobs_seen, avg_fit, apply_rate
- `v_current_session_stats` — live KPIs scoped to the active session

## Conventions

- Always open the DB **read-only** in refresh scripts: `duckdb.connect(path, read_only=True)`.
- Refresh scripts live in `.jetro/scripts/`. They print JSON to stdout. The
  JSON is delivered to the bound frame via `jet:refresh` CustomEvent (NOT
  `message`). Read it as `e.detail`.
- Frames go in `.jetro/frames/<name>.html`. Use Plotly via `<script src>` (CDN
  shimmed locally by Jetro). NEVER inline Plotly source.
- Refresh interval ≥ 30s for historical aggregates; ≥ 5s for live KPIs.

## Common patterns

### "Top N most-asked skills"
```sql
SELECT display_name, jobs_asking
FROM v_skill_gaps
ORDER BY jobs_asking DESC LIMIT 20;
```

### "My response/apply rate by company size or sector"
Not in MVP schema. Requires extending `jobs` with a `sector` column or joining
a future `companies` table.

### "Best fit unrated jobs (need decision)"
```sql
SELECT title, company, fit_score, recommendation
FROM v_job_analysis
WHERE latest_decision IS NULL AND fit_score >= 70
ORDER BY fit_score DESC LIMIT 25;
```

## Anti-patterns

- Do NOT write `jobs` directly without `v_job_analysis` when you also want fit data
- Do NOT compute matched/missing client-side; always join `job_skills` against
  `user_skills` in SQL
- Do NOT bind a Python refresh script to a frame that already subscribes to a
  C2 wire — pick one mechanism per frame
```

- [ ] **Step 2: Commit**

```bash
git add .jetro/skills/jobscope_dashboard.md
git commit -m "feat(skill): jobscope_dashboard skill teaches dashboard-building from DuckDB"
```

### Task 9.2: Seed the DB with 50+ jobs for demo

**Files:** (runtime only — no code)

This is a manual step before the demo recording. Run the bot for ~30 minutes
to accumulate real evaluated jobs.

- [ ] **Step 1: Reset to clean state**

```bash
python -m jobscope reset --confirm
python -m jobscope seed-skills
python -m jobscope parse-resume
```

- [ ] **Step 2: Run the bot**

```bash
python -m jobscope run
```

Iterate until at least 50 jobs are evaluated across all 5 search terms. Make
real decisions; this becomes the data the historical dashboard shows.

- [ ] **Step 3: Verify aggregates render**

Open the Historical Dashboard canvas. All 4 charts should populate.
Open the Live Cockpit canvas. KPI bar should show realistic counts.

### Task 9.3: Deploy historical dashboard

**Files:** (Jetro tool call, no new code)

- [ ] **Step 1: Fetch the Deploy skill for current syntax**

Call: `jet_skill({ name: "Deploy App" })` and follow its instructions.

- [ ] **Step 2: Deploy**

`jet_deploy({ action:'start', projectSlug:'jobscope', canvasId: <historical_id> })`

Verify the resulting public URL works in an incognito window — all 4 charts
should load and refresh.

- [ ] **Step 3: Record the URL in PROGRESS.md** under "Deployments".

### Task 9.4: Publish historical dashboard as LDF

**Files:** (Jetro tool call)

- [ ] **Step 1: Fetch the LDF skill**

Call: `jet_skill({ name: "Publish LDF" })`.

- [ ] **Step 2: Publish each historical frame**

Use `jet_doc` to publish the historical canvas as a `.ldf` file. Record the
file path in PROGRESS.md.

### Task 9.5: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# JobScope

Personal LinkedIn job-market intelligence — a Selenium scraper that calls
Gemini per job description, writes to DuckDB, and renders a live cockpit and
historical dashboard on Jetro canvases. Decisions happen via a tkinter popup.
**It never clicks Apply.**

Built as a Round 2 submission for Berrywise (berrywise.ai).

## Quick start

1. Install Python 3.11 and Chrome (any recent stable).
2. Clone, create a venv, install:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -e ".[dev]"
   ```
3. Copy `.env.example` to `.env` and fill in:
   - `LINKEDIN_USERNAME`, `LINKEDIN_PASSWORD`
   - `GEMINI_API_KEYS` — comma-separated. Get free keys at https://aistudio.google.com/app/apikey
4. One-time setup:
   ```bash
   python -m jobscope seed-skills
   python -m jobscope parse-resume
   ```
5. Open this folder in VS Code with the Jetro extension. Open the **Live
   Cockpit** and **Historical Dashboard** canvases under projects/jobscope.
6. Start the bot:
   ```bash
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
- `docs/superpowers/specs/2026-05-25-jobscope-design.md` — full design spec
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with quick-start, commands, configuration"
```

### Task 9.6: Update PROGRESS.md and final smoke

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Append today's completion entry**

Update PROGRESS.md log section with new entry summarizing what was built and
linking to the deployed URL + LDF path.

- [ ] **Step 2: Final smoke on a clean machine**

On a fresh Windows install (or VM):
1. Clone repo
2. `python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"`
3. Copy `.env.example` to `.env` and fill in credentials
4. `python -m jobscope seed-skills && python -m jobscope parse-resume`
5. `python -m jobscope run`
6. Confirm: Chrome opens, login succeeds, first job analyzed, popup appears,
   canvas updates within 3 seconds of decision.

If anything breaks, fix it BEFORE recording the demo.

- [ ] **Step 3: Record the demo (5 minutes)**

Narrate the workflow: open VS Code, show Live Cockpit + Historical Dashboard
side by side, run the bot for 3-5 jobs, demonstrate the popup, show how
historical aggregates update, then show the deployed public URL in a browser.

- [ ] **Step 4: Final commit**

```bash
git add PROGRESS.md
git commit -m "docs(progress): MVP complete; deploy URL + LDF path recorded"
```

### Task 9.7: Delete the reference repo (post-MVP)

**Files:** (destructive — confirm with user first)

- [ ] **Step 1: Confirm with user before deleting**

The reference repo `auto_job_applier_linkedIn/` is no longer needed. Confirm
with the user that everything in `jobscope/` is self-contained, then:

```bash
rm -rf auto_job_applier_linkedIn
git add -A
git commit -m "chore: remove auto_job_applier_linkedIn reference (donor only)"
```

---

## Self-review (against the spec)

| Spec section | Covered by |
|---|---|
| §1 Locked-in decisions | Honored throughout — Selenium-only (Task 5.3), canvas read-only (Phase 8), tkinter popup (Task 6.2), two canvases (Task 8.1), Gemini Flash Lite + rotation (Task 4.3), config in `jobscope/config.py` + `.env` (Task 1.3-1.4), DuckDB ≥ 1.0 (Task 1.1 deps), `current_job.json` atomic write (Task 6.1) |
| §2 Architecture (3 units + invariants) | Tasks in Phases 4 (AI), 5 (scraper), 2 (DB), 7 (orchestrator wiring) |
| §2 Live-canvas C2 fan-out | Task 8.3 (hub) + 8.4 (subscribers) + `enableC2` in Task 8.1 |
| §3.1 current_job.json schema | Task 6.1 + orchestrator state helpers in 7.1 |
| §3.2 Refresh cadence | Live 2000ms (8.3), KPIs 5000ms (8.5), historical 30000ms (8.6) |
| §3.3 Staleness handling | refresh_current_job.py computes `_meta.staleness` (8.2); live_bot_status renders it (8.4) |
| §3.4 Reset flavors | CLI commands `clear-live` + `reset --confirm` (Task 7.2) |
| §3.5 Bot lifecycle | orchestrator.py covers idle → loading → analyzing → analyzed → decided → stopped (7.1) |
| §4 Schema | Task 2.1, 2.2, 2.3, 2.5 |
| §4 Connection rules | open_rw / open_ro split (2.3); refresh scripts use read_only=True (8.5, 8.6) |
| §5 Gemini prompt + Pydantic + retry/rotation | Tasks 4.1, 4.2, 4.3, 4.4 |
| §6 File layout | Phases 1-7 build exactly the layout |
| §6 What gets lifted | Tasks 5.1-5.7 lift selectors/regex/login/clickers |
| §7 Testing strategy | TDD on ai/schema, ai/client, ai/analyzer, db/repo, db/views, state/snapshot, extract.extract_years; smoke on scraper, popup, canvas |
| §7 Failure matrix | analyzer retry+rotation (4.3-4.4); orchestrator try/except + state=error (7.1); login verification callback (5.3) |
| §7 Logging | utils/logging.py (1.5); orchestrator uses it (7.1) |
| §7 On-canvas observability | live_bot_status.html (8.4) |
| §7 Pre-demo verification | Tasks 9.2-9.6 |
| §8 Out of scope | Not implemented (as intended) |
| §10 Definition of done | Tasks 9.2-9.6 collectively verify |

**Placeholder scan:** none.

**Type consistency:** function names `analyze`, `open_rw`/`open_ro`, `init_schema`,
`write_snapshot`/`read_snapshot`, `upsert_job`, `record_decision`, `start_session`,
`end_session`, `seed_skills_canonical`, `replace_job_skills`, `insert_analysis`
appear consistently across tasks. Pydantic field names match between schema
(4.1), prompt (4.2), analyzer (4.4), and repo (2.5). DuckDB column names in
schema.sql (2.1) match views (2.2) and repo (2.5).

**Spec gap found and added:** Selenium captcha/verification flow needed a UI;
added `_wait_for_user_verify` in orchestrator.py (Task 7.1) and `login-only`
CLI command (Task 7.2) — both serve the captcha-wall failure mode in spec §7.2.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-25-jobscope-implementation.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 1-week MVP with this many tasks (~40).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Slower but everything visible in one session.

**Which approach?**
