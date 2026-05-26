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
