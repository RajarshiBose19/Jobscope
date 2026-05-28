import json
from pathlib import Path
import duckdb
from jobscope import config
from jobscope.db import repo
from jobscope.utils.logging import get_logger

log = get_logger("profile.normalize")

REQUIRED = {"full_name", "experience_years", "expected_ctc_lpa", "skills"}

def load_profile(profile_path: Path) -> dict:
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    missing = REQUIRED - set(data.keys())
    if missing:
        raise ValueError(f"profile.json missing required keys: {missing}")
    if not isinstance(data["skills"], list) or not data["skills"]:
        raise ValueError("profile.skills must be a non-empty list")
    overrides = {
        "experience_years": config.EXPERIENCE_YEARS,
        "current_ctc_lpa":  config.CURRENT_CTC_LPA,
        "expected_ctc_lpa": config.EXPECTED_CTC_LPA,
        "current_location": config.CURRENT_CITY,
        "full_name":        config.FULL_NAME,
        "notice_period_months": config.NOTICE_PERIOD_MONTHS,
    }
    for k, v in overrides.items():
        if v is None:
            continue
        old = data.get(k)
        if old != v:
            log.info("profile_override_from_config",
                     extra={"field": k, "profile_value": old, "config_value": v})
            data[k] = v
    try:
        from jobscope.profile.parse_resume import extract_text
        resume_text = extract_text(config.RESUME_PDF)
        resume_text = "\n".join(
            line.strip() for line in resume_text.splitlines() if line.strip()
        )
        data["resume_text"] = resume_text
        log.info("resume_loaded", extra={"chars": len(resume_text)})
    except Exception as e:
        log.warning("resume_load_failed", extra={"err": str(e)})
        data["resume_text"] = ""
    return data

def sync_profile_to_db(conn: duckdb.DuckDBPyConnection, profile: dict) -> None:
    repo.upsert_user_profile(conn, profile)
    repo.replace_user_skills(conn, profile["skills"])
