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
