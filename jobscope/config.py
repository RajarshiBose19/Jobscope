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
