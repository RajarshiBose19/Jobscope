import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT     = Path(__file__).resolve().parent.parent
PROJECT_ROOT  = REPO_ROOT / "projects" / "jobscope"
DB_PATH       = PROJECT_ROOT / "jobscope.duckdb"
PROFILE_PATH  = PROJECT_ROOT / "profile.json"
RESUME_PDF    = PROJECT_ROOT / "resume.pdf"
SNAPSHOT_PATH = PROJECT_ROOT / "state" / "current_job.json"
AGG_SESSION_KPIS_PATH       = PROJECT_ROOT / "state" / "session_kpis.json"
AGG_SKILL_GAPS_PATH         = PROJECT_ROOT / "state" / "skill_gaps.json"
AGG_FIT_DISTRIBUTION_PATH   = PROJECT_ROOT / "state" / "fit_distribution.json"
AGG_SALARY_MAP_PATH         = PROJECT_ROOT / "state" / "salary_map.json"
AGG_SEARCH_TERM_REPORT_PATH = PROJECT_ROOT / "state" / "search_term_report.json"
CRASHED_DIR   = PROJECT_ROOT / "state" / "crashed"
LOG_PATH      = REPO_ROOT / "logs" / "jobscope.log"

LINKEDIN_USERNAME = os.environ.get("LINKEDIN_USERNAME", "")
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "")
GEMINI_API_KEYS   = [
    k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()
]

SEARCH_TERMS = [
    "ASP.NET Developer", "AI Engineer", "Software Developer",
    "Full Stack Developer", "AWS Engineer",
]
SEARCH_LOCATION   = "Bengaluru, Karnataka, India"
DATE_POSTED       = "Past 24 hours"
EASY_APPLY_ONLY   = True
EXPERIENCE_LEVELS = ["Entry level", "Associate", "Mid-Senior level"]
JOB_TYPES         = ["Full-time"]
ON_SITE           = ["Remote", "Hybrid", "On-site"]
SWITCH_AFTER      = 5
MAX_POPUPS_PER_TERM = 50

CLICK_GAP_SEC      = 2
STEALTH_MODE       = True
RUN_IN_BACKGROUND  = False
DISABLE_EXTENSIONS = True
CHROME_VERSION_MAIN: int | None = 148
CHROME_PROFILE_DIR = REPO_ROOT / ".jetro" / "credentials" / "chrome-profile"

BLACKLISTED_COMPANIES: set[str] = set()
JD_BAD_WORDS: list[str] = [
    "",
]
EXPERIENCE_BUFFER_YEARS: int | None = 1
RECENT_ANALYSIS_DAYS: int = 14

FULL_NAME            = os.environ.get("FULL_NAME", "Your Name")
PHONE                = os.environ.get("PHONE", "")
CURRENT_CITY         = os.environ.get("CURRENT_CITY", "Bengaluru")
CURRENT_CTC_LPA      = float(os.environ.get("CURRENT_CTC_LPA", "0"))
EXPECTED_CTC_LPA     = float(os.environ.get("EXPECTED_CTC_LPA", "0"))
EXPERIENCE_YEARS     = float(os.environ.get("EXPERIENCE_YEARS", "0"))
NOTICE_PERIOD_MONTHS = int(os.environ.get("NOTICE_PERIOD_MONTHS", "1"))

GEMINI_MODEL       = "gemini-2.5-flash-lite"
PROMPT_VERSION     = "3.2.0"
GEMINI_TIMEOUT_SEC = 30
GEMINI_TEMPERATURE = 0.2

LIVE_REFRESH_MS         = 2000
HISTORICAL_REFRESH_MS   = 30000
SESSION_KPI_REFRESH_MS  = 5000
SNAPSHOT_STALE_WARN_SEC = 10
SNAPSHOT_STALE_FAIL_SEC = 60

def ensure_dirs() -> None:
    for d in (PROJECT_ROOT / "state", CRASHED_DIR, LOG_PATH.parent):
        d.mkdir(parents=True, exist_ok=True)
